#!/usr/bin/python
import asyncio
import base64
import json
import logging
import os

import aiohttp
from aiohttp import client, web
from multidict import MultiDict, MultiDictProxy

from mockbin.logfilter import *
from mockbin.promstats import *
from mockbin.tracing import *

baselevel = logging.DEBUG if os.environ.get("DEBUG", False) else logging.INFO
logger = FilteredLogger(__name__, baselevel=baselevel)

instrument()
tracer = trace.get_tracer("mockbin")


@web.middleware
async def opentelemetry(request, handler):
    _ctx = get_tracecontext(dict(request.headers.copy()))

    tracer = trace.get_tracer("aiohttp.server")
    with tracer.start_as_current_span(
        "aiohttp.handler",
        kind=trace.SpanKind.SERVER,
        context=_ctx,
        attributes={
            "method": request.method,
            "url": str(request.url),
            "scheme": request.scheme,
            "forwarded": request.forwarded,
            "downstream": request.remote,
            "path": request.path,
            "query": str(dict(request.query)),
            "headers": str(dict(request.headers)),
            "content-type": str(request.content_type),
            "content-length": str(request.content_length),
        },
    ) as span:
        TRACINGCALLS_TOTAL.inc()
        return await handler(request)


app = web.Application(middlewares=[opentelemetry])
app["outlier_enabled"] = False


async def metrics(req):
    return web.Response(
        status=200,
        headers={
            "Content-Type": "application/openmetrics-text",
            "MimeType": "application/openmetrics-text",
        },
        body=generate_metrics(),
    )


async def health(req):
    return web.Response(status=200, body="OK")


@measure
async def handler(req):
    status = 200
    headers = req.headers.copy()
    _ctx = get_tracecontext(headers=dict(headers))
    try:
        with tracer.start_as_current_span(
            "downstream request",
            attributes=dict(headers),
        ) as span:
            _sctx = span.get_span_context()
            TRACINGCALLS_TOTAL.inc()
            traceparent = get_traceparent(_sctx)
            span.set_status(StatusCode.OK)
            headers = TraceContextTextMapPropagator().inject(dict(headers), _ctx)
            if headers == None:
                headers = req.headers.copy()
                _ctx = span.get_span_context()
                headers["traceparent"] = traceparent.header
                headers = dict(headers) | traceparent.xb3
            if app["outlier_enabled"]:
                logger.info(f"failing for outlier detection", _ctx=_ctx)
                span.add_event(
                    "outlier-detection",
                    attributes={"failing": "outlier-detection-test"},
                )
                status = 503
            HTTP_RESPONSES_TOTAL.labels(
                req.method, req.path, status, get_source(headers), "-"
            ).inc()
            return web.Response(
                status=status,
                headers={"traceparent": traceparent.header} | traceparent.xb3,
                body=json.dumps({"headers": dict(headers), "env": dict(os.environ)}),
            )
    except Exception as perr:
        HTTP_RESPONSES_TOTAL.labels(
            req.method, req.path, 503, get_source(headers), "-"
        ).inc()
        return web.Response(
            status=503,
            body=str(perr),
            headers={"traceparent": get_traceparent(_ctx).header},
        )


@measure
async def handler_logging(req):
    status = 200
    headers = req.headers.copy()
    _ctx = get_tracecontext(headers=dict(headers))
    try:
        with tracer.start_as_current_span(
            "downstream request",
            attributes=dict(headers),
        ) as span:
            _sctx = span.get_span_context()
            logger.info(f"first log in context", _ctx=_ctx)
            TRACINGCALLS_TOTAL.inc()
            traceparent = get_traceparent(_sctx)
            logger.warning(
                f"second compiled traceparent {traceparent.header} in context",
                _ctx=_ctx,
            )
            span.set_status(StatusCode.OK)
            headers = TraceContextTextMapPropagator().inject(dict(headers), _ctx)
            if headers == None:
                logger.debug(f"third injection traceparent into headers", _ctx=_ctx)
                headers = req.headers.copy()
                _ctx = span.get_span_context()
                headers["traceparent"] = traceparent.header
                headers = dict(headers) | traceparent.xb3
            logger.levels[logging.DEBUG] = True
            logger.logger.setLevel(logging.DEBUG)
            logger.debug(f"forth hitting metrics increment", _ctx=_ctx)
            logger.logger.setLevel(logging.INFO)
            logger.levels[logging.DEBUG] = False
            HTTP_RESPONSES_TOTAL.labels(
                req.method, req.path, status, get_source(headers), "-"
            ).inc()
            logger.error(f"fifth returning {status} for request", _ctx=_ctx)
            span.add_event("log messages sent")
            return web.Response(
                status=status,
                body=json.dumps({"headers": dict(headers), "env": dict(os.environ)}),
                headers={"traceparent": traceparent.header} | traceparent.xb3,
            )
    except Exception as perr:
        logger.error(f"Exception {perr}", _ctx=_ctx)
        HTTP_RESPONSES_TOTAL.labels(
            req.method, req.path, 503, get_source(headers), "-"
        ).inc()
        return web.Response(
            status=503,
            body=str(perr),
            headers={"traceparent": get_traceparent(_ctx).header},
        )


def adjust_headers(headers):
    reqheaders = headers.copy()
    for h in (
        "Transfer-Encoding",
        "Content-Length",
        "Content-Encoding",
        "Accept-Encoding",
        "Origin",
        "Referer",
        "Host",
        "Vary",
    ):
        try:
            del reqheaders[h]
        except Exception as e:
            pass
    return reqheaders


def flatten_struct(headers):
    newheaders = {}
    for h in headers:
        if isinstance(headers[h], dict):
            newheaders.update(dict(flatten_struct(headers[h])))
            continue
        newheaders[h] = headers[h]
    return newheaders


def get_source(headers):
    return headers.get("x-forwarded-for", "").split(",")[0]


@measure
async def handler_proxy(req):
    status = 200
    headers = req.headers.copy()
    _ctx = get_tracecontext(headers=dict(headers))
    traceparent = get_traceparent(_ctx).header
    try:
        _reqdata = await req.post()
        reqdata = _reqdata.copy()
        reqquery = req.query.copy()
        rbody = []
        print(f"reqdata proxy type {type(reqdata)} {reqdata.get('proxy')}")
        try:
            proxyurls = reqdata.get("proxy").split(",")
        except:
            proxyurls = ["http://localhost:8080/no-proxy"]
        if len(proxyurls) >= 1:
            dreq = proxyurls.pop(0)
            with tracer.start_as_current_span(
                "downstream request",
                attributes=(
                    dict(flatten_struct(headers))
                    | dict(flatten_struct(reqdata))
                    | dict(flatten_struct(reqquery))
                ),
            ) as span:
                _c = span.get_span_context()
                TRACINGCALLS_TOTAL.inc()
                traceparent = get_traceparent(_c).header
                reqparams = {
                    "method": (
                        reqdata.get("method", "GET")
                        if not str(dreq).endswith("/proxy/")
                        else "POST"
                    ),
                    "url": str(dreq),
                    "allow_redirects": True,
                    "ssl": False,
                    "data": dict(proxy=",".join(proxyurls)),
                    "headers": dict(adjust_headers(headers)),
                }
                span.set_status(StatusCode.OK)
                status = 200
                with tracer.start_as_current_span(
                    "upstream request",
                    attributes=dict(flatten_struct(reqparams)),
                ) as uspan:
                    TRACINGCALLS_TOTAL.inc()
                    try:
                        logger.info(f"calling {reqparams['url']}", _ctx=_ctx)
                        reqparams["headers"].update(
                            {"traceparent": get_traceparent(_c).header}
                        )
                        logger.error(f"reqparams {reqparams}", _ctx=_ctx)
                        async with client.request(**reqparams) as resp:
                            urbody = await resp.read()
                            rheaders = dict(resp.headers.copy())
                            uspan.add_event(
                                "upstream response",
                                attributes={
                                    "status": resp.status,
                                }
                                | dict(flatten_struct(rheaders)),
                            )
                            try:
                                dbody = urbody.decode("utf8")
                            except:
                                pass
                            rbody = {
                                "proxy": dreq,
                                "headers": rheaders
                                | {"traceparent": get_traceparent(_ctx).header},
                                "body": dbody,
                            }
                            uspan.set_status(StatusCode.OK)
                            status = resp.status
                    except Exception as upsterr:
                        logger.error(f"upstream response Error {upsterr}", _ctx=_ctx)
                        status = 503
                        uspan.record_exception(upsterr)
                        uspan.set_status(StatusCode.ERROR)

        HTTP_RESPONSES_TOTAL.labels(
            req.method, req.path, 503, get_source(headers), "-"
        ).inc()
        traceparent = get_traceparent(_ctx)
        return web.Response(
            status=status,
            headers={
                "Content-type": "application/json",
                "traceparent": traceparent.header,
            }
            | traceparent.xb3,
            body=json.dumps(rbody),
        )

    except Exception as perr:
        logger.error(f"Exception {perr}", _ctx=_ctx)
        HTTP_RESPONSES_TOTAL.labels(
            req.method, req.path, 503, get_source(headers), "-"
        ).inc()
        traceparent = get_traceparent(_ctx)
        return web.Response(
            status=503,
            headers={"traceparent": traceparent.header} | traceparent.xb3,
            body=str(perr),
        )


@measure
async def handler_exception(req):
    status = 200
    headers = req.headers.copy()
    _ctx = get_tracecontext(headers=dict(headers))
    try:
        with tracer.start_as_current_span(
            "downstream request",
            attributes=dict(headers),
        ) as span:
            _sctx = span.get_span_context()
            TRACINGCALLS_TOTAL.inc()
            traceparent = get_traceparent(_sctx)
            try:
                1 / 0
            except ZeroDivisionError as error:
                span.record_exception(error)
                span.set_status(StatusCode.ERROR)
                try:
                    status = int(req.path.split("/")[-1])
                except:
                    status = 500
                if headers == None:
                    headers = req.headers.copy()
                    _ctx = span.get_span_context()
                    headers["traceparent"] = traceparent.header
                    headers = dict(headers) | traceparent.xb3
                HTTP_RESPONSES_TOTAL.labels(
                    req.method, req.path, status, get_source(headers), "-"
                ).inc()
                return web.Response(
                    status=status,
                    body=json.dumps(
                        {"headers": dict(headers), "env": dict(os.environ)}
                    ),
                    headers={"traceparent": traceparent.header} | traceparent.xb3,
                )
    except Exception as perr:
        logger.error(f"Exception {perr}", _ctx=_ctx)
        HTTP_RESPONSES_TOTAL.labels(
            req.method, req.path, 503, get_source(headers), "-"
        ).inc()
        traceparent = get_traceparent(_ctx)
        return web.Response(
            status=503,
            body=str(perr),
            headers={"traceparent": traceparent.header} | traceparent.xb3,
        )


@measure
async def handler_alert_receiver(req):
    status = 200
    headers = req.headers.copy()
    _ctx = get_tracecontext(headers=dict(headers))
    try:
        with tracer.start_as_current_span(
            "downstream request",
            attributes=dict(headers),
        ) as span:
            try:
                data = await req.json()
            except:
                data = await req.read()
                logger.error(
                    f"didn't receive json from downstream only body {body}", _ctx=_ctx
                )
            TRACINGCALLS_TOTAL.inc()
            try:
                with tracer.start_as_current_span(
                    "alert-receiver",
                    attributes={
                        "status": data.get("status"),
                        "count": len(data.get("alerts", [])),
                        "origin": get_source(headers),
                    },
                ) as aspan:
                    logger.debug(f"data for trace {dict(data)}", _ctx=_ctx)
                    TRACINGCALLS_TOTAL.inc()
                    for alert in data.get("alerts", []):
                        aspan.add_event("alert", attributes=dict(flatten_struct(alert)))
                        if data.get("status") == "resolved":
                            aspan.set_status(StatusCode.OK)
                        else:
                            aspan.set_status(StatusCode.ERROR)
                    logger.info(
                        f"received {len(data.get('alerts',[]))} from {get_source(headers)}",
                        _ctx=_ctx,
                    )
                span.set_attribute("cluster", alert.get("region", "local"))
                span.set_status(StatusCode.OK)
            except Exception as alterr:
                logger.error(f"Exception handling alert to trace {alterr}", _ctx=_ctx)
                span.record_exception(alterr)
                span.set_status(StatusCode.ERROR)

            HTTP_RESPONSES_TOTAL.labels(
                req.method, req.path, 201, get_source(headers), "-"
            ).inc()
            return web.Response(
                status=201,
                headers={"traceparent": get_traceparent(_ctx).header},
            )
    except Exception as perr:
        logger.error(f"Exception handling alert to trace {perr}", _ctx=_ctx)
        HTTP_RESPONSES_TOTAL.labels(
            req.method, req.path, 503, get_source(headers), "-"
        ).inc()
        return web.Response(
            status=503,
            body=str(perr),
            headers={"traceparent": get_traceparent(_ctx).header},
        )


@measure
async def handler_outlier(req):
    status = 200
    headers = req.headers.copy()
    _ctx = get_tracecontext(headers=dict(headers))
    try:
        with tracer.start_as_current_span(
            "downstream request",
            attributes=dict(headers) | {"method": req.method},
        ) as span:
            TRACINGCALLS_TOTAL.inc()
            if req.method == "PUT":
                app["outlier_enabled"] = True
                span.add_event("outlier enabled")
            elif req.method == "DELETE":
                app["outlier_enabled"] = False
                span.add_event("outlier disabled")
    except Exception as perr:
        logger.error(f"Exception handling alert to trace {perr}", _ctx=_ctx)
        HTTP_RESPONSES_TOTAL.labels(
            req.method, req.path, 503, get_source(headers), "-"
        ).inc()
        return web.Response(
            status=503,
            body=str(perr),
            headers={"traceparent": get_traceparent(_ctx).header},
        )
    HTTP_RESPONSES_TOTAL.labels(
        req.method, req.path, 201, get_source(headers), "-"
    ).inc()
    return web.Response(
        status=201,
        headers={"traceparent": get_traceparent(_ctx).header},
    )


async def app_factory():
    app.router.add_route("*", "/health", health)
    app.router.add_route("GET", "/metrics", metrics)
    app.router.add_route("*", "/exception/{tail:.*}", handler_exception)
    app.router.add_route("*", "/logging/{tail:.*}", handler_logging)
    app.router.add_route("*", "/proxy/{tail:.*}", handler_proxy)
    app.router.add_route("*", "/{tail:.*}", handler)
    app.router.add_route("PUT", "/outlier", handler_outlier)
    app.router.add_route("DELETE", "/outlier", handler_outlier)
    app.router.add_route("*", "/webhook/alert-receiver", handler_alert_receiver)
    app["outlier_enabled"] = False
    return app


if __name__ == "__main__":
    print(
        f"Running on {os.environ.get('API', f'http://0.0.0.0:{os.environ.get("PORT",8080)}')}"
    )
    web.run_app(app_factory(), port=int(os.environ.get("PORT", 8080)))
