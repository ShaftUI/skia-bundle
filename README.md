# Skia Artifact Bundle Builder

This Python script builds a Swift Package Manager artifact bundle for pre-compiled Skia binaries.

## Features

- Downloads Skia binaries from GitHub releases for multiple platforms:
  - macOS Universal (x86_64 + arm64)
  - Linux x64
  - Linux ARM64
  - Windows x64
- Extracts and organizes binaries and headers
- Creates a complete artifact bundle with proper Swift Package Manager structure
- Includes all Skia headers (339+ header files)
- Generates umbrella header for easy integration

## Usage

```bash
# Build artifact bundle with default Skia version (m126-6bfb13368b)
python3 build_skia_bundle.py

# Specify a different Skia version
python3 build_skia_bundle.py --version m125-5bfb13368a

# Specify custom output directory
python3 build_skia_bundle.py --output custom_skia.artifactbundle

# Create a ZIP file for easy distribution
python3 build_skia_bundle.py --zip

# Combine options
python3 build_skia_bundle.py --version m127-7bfb13368c --output custom.artifactbundle --zip

# Get help
python3 build_skia_bundle.py --help
```

### Options

- `--version`: Skia version to download (default: `m126-6bfb13368b`)
- `--output`: Output directory for the artifact bundle (default: `skia.artifactbundle`)
- `--zip`: Create a ZIP file of the artifact bundle for easy distribution

## Output Structure

The script creates an artifact bundle with the following structure:

```
skia.artifactbundle/
├── info.json                    # Swift Package Manager metadata
├── module.modulemap             # Module map for Swift integration
├── include/                     # All Skia headers
│   ├── skia.h                   # Umbrella header
│   ├── core/                    # Core Skia headers
│   ├── gpu/                     # GPU-related headers
│   ├── effects/                 # Effects and filters
│   └── ...                      # Other header directories
├── macos-universal/
│   └── libskia.a               # Universal binary for macOS
├── linux-x64/
│   └── libskia.a               # Linux x86_64 binary
├── linux-aarch64/
│   └── libskia.a               # Linux ARM64 binary
└── windows-x64/
    └── skia.lib                # Windows x64 binary
```

## Integration in Swift Package

Add the artifact bundle to your Swift package by including it in your `Package.swift`:

```swift
let package = Package(
    name: "YourPackage",
    products: [
        .library(name: "YourLibrary", targets: ["YourTarget"]),
    ],
    targets: [
        .target(
            name: "YourTarget",
            dependencies: ["skia"]
        ),
        .binaryTarget(
            name: "skia",
            path: "path/to/skia.artifactbundle"
        ),
    ]
)
```

## Requirements

- Python 3.6+
- Internet connection to download Skia binaries
- Sufficient disk space (~500MB for temp files and artifact bundle)

## GitHub Actions CI/CD

This repository includes a GitHub Actions workflow that automatically builds and releases Skia artifact bundles.

### Automatic Builds

The workflow is triggered by:

1. **Releases**: When you create a GitHub release, it automatically builds the artifact bundle
2. **Manual Dispatch**: You can manually trigger builds with custom Skia versions
3. **Push to Main**: Builds are triggered when the script or workflow files are updated

### Manual Release

To create a release with a specific Skia version:

1. Go to the "Actions" tab in your GitHub repository
2. Select "Build Skia Artifact Bundle" workflow
3. Click "Run workflow"
4. Specify the Skia version (e.g., `m127-7bfb13368c`)
5. Optionally specify a release tag to upload to

### Workflow Features

- **Multi-platform builds**: Creates artifact bundles for all supported platforms
- **Automatic uploads**: ZIP files are uploaded to GitHub releases
- **Artifact storage**: Build artifacts are stored for 30 days for download
- **Detailed release notes**: Auto-generated documentation with usage instructions

## Temporary Files

The script downloads files to a `./temp` directory for inspection. These files are not automatically cleaned up, allowing you to examine the contents if needed.

## Based On

This script is based on the logic from `skiadownload.swift` and follows the artifact bundle format specified in [Swift Evolution SE-0482](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0482-swiftpm-static-library-binary-target-non-apple-platforms.md).