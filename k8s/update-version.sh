#!/bin/bash
# Script to update image version in Kubernetes manifests
# Usage: ./update-version.sh [version]
# If no version provided, reads from ../VERSION file

set -e

# Get version from argument or VERSION file
if [ -n "$1" ]; then
  VERSION="$1"
elif [ -f ../VERSION ]; then
  VERSION=$(cat ../VERSION | tr -d '[:space:]')
else
  echo "ERROR: No version provided and ../VERSION file not found"
  echo "Usage: $0 [version]"
  exit 1
fi

echo "Updating image version to: $VERSION"

# Update kustomization.yaml
if [ -f kustomization.yaml ]; then
  sed -i.bak "s/newTag: .*/newTag: $VERSION/" kustomization.yaml
  rm -f kustomization.yaml.bak
  echo "✓ Updated kustomization.yaml"
fi

# Update deployment.yaml
if [ -f deployment.yaml ]; then
  sed -i.bak "s|image: quay.io/tjungbau/mockbin:.*|image: quay.io/tjungbau/mockbin:$VERSION|" deployment.yaml
  rm -f deployment.yaml.bak
  echo "✓ Updated deployment.yaml"
fi

echo ""
echo "Image version updated to $VERSION in all manifests"
echo "Don't forget to commit these changes!"

