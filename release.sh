#!/bin/bash
set -e
VERSION=$(date +%Y.%m.%d)-$(git rev-parse --short HEAD)
echo "🏷️ Creating release $VERSION"

cd frontend && npm run build && cd ..
git add .
git commit -m "📦 Release $VERSION" || true
git tag -a "v$VERSION" -m "Release v$VERSION"
git push origin main --tags

echo "✅ Released. Upload frontend/dist/ to GitHub Releases manually or via Actions."
