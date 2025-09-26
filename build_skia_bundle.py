#!/usr/bin/env python3
"""
Script to build an artifact bundle for pre-compiled Skia binaries.
Downloads Skia binaries from GitHub releases and packages them into a Swift Package Manager artifact bundle.
"""

import argparse
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Dict, List
from urllib.request import urlretrieve
from urllib.parse import urlparse


def get_download_info(version: str) -> Dict[str, Dict[str, str]]:
    """
    Get download URLs and file information for each platform.
    Based on skiadownload.swift logic.
    """
    
    # Repository selection based on platform
    shaftui_repo = "https://github.com/ShaftUI/skia-pack"
    jetbrains_repo = "https://github.com/JetBrains/skia-pack"
    
    platforms = {
        "macos-universal": {
            "repo": jetbrains_repo,
            "arch": "arm64",  # Will be universal binary
            "os": "macos",
            "lib_name": "libskia.a",
            "triple": ["x86_64-apple-macosx", "arm64-apple-macosx"]
        },
        "linux-x64": {
            "repo": shaftui_repo,
            "arch": "x64", 
            "os": "linux",
            "lib_name": "libskia.a",
            "triple": ["x86_64-unknown-linux-gnu"]
        },
        "linux-aarch64": {
            "repo": shaftui_repo,
            "arch": "arm64",
            "os": "linux", 
            "lib_name": "libskia.a",
            "triple": ["aarch64-unknown-linux-gnu"]
        },
        "windows-x64": {
            "repo": shaftui_repo,
            "arch": "x64",
            "os": "windows",
            "lib_name": "skia.lib",
            "triple": ["x86_64-unknown-windows-msvc"]
        }
    }
    
    download_info = {}
    for platform, info in platforms.items():
        url = f"{info['repo']}/releases/download/{version}/Skia-{version}-{info['os']}-Release-{info['arch']}.zip"
        download_info[platform] = {
            "url": url,
            "lib_name": info["lib_name"],
            "triple": info["triple"],
            "extract_path": f"out/Release-{info['os']}-{info['arch']}"
        }
    
    return download_info


def download_and_extract(url: str, temp_dir: Path, platform: str, extract_path: str) -> Path:
    """Download and extract Skia binary for a specific platform."""
    
    print(f"Downloading {platform} from {url}")
    
    zip_path = temp_dir / f"{platform}.zip"
    platform_dir = temp_dir / platform
    
    # Download the ZIP file
    try:
        urlretrieve(url, zip_path)
        print(f"Downloaded {platform} to {zip_path}")
    except Exception as e:
        print(f"Failed to download {platform}: {e}")
        return None
    
    # Extract the ZIP file
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Extract only files from the specific release path
            for member in zip_ref.namelist():
                if member.startswith(extract_path):
                    # Remove the extract_path prefix from the member name
                    relative_path = member[len(extract_path):].lstrip('/')
                    if relative_path:  # Skip empty paths (directories)
                        target_path = platform_dir / relative_path
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        with zip_ref.open(member) as source, open(target_path, 'wb') as target:
                            shutil.copyfileobj(source, target)
                        print(f"Extracted {relative_path}")
        
        print(f"Extracted {platform} to {platform_dir}")
        return platform_dir
        
    except Exception as e:
        print(f"Failed to extract {platform}: {e}")
        return None


def create_info_json(bundle_dir: Path, version: str, download_info: Dict, all_libraries: Dict) -> None:
    """Create the info.json file for the artifact bundle."""
    
    artifacts = {}
    
    # Get all unique library names across platforms
    all_lib_names = set()
    for platform_libs in all_libraries.values():
        for lib in platform_libs:
            all_lib_names.add(lib["lib_name"])
    
    # Create artifact entries for each library
    for lib_name in sorted(all_lib_names):
        variants = []
        
        # Find variants for this library across platforms
        for platform, platform_libs in all_libraries.items():
            platform_info = download_info[platform]
            
            # Find this library in the platform
            lib_info = None
            for lib in platform_libs:
                if lib["lib_name"] == lib_name:
                    lib_info = lib
                    break
            
            if lib_info:
                lib_path = f"{platform}/{lib_info['file_name']}"
                
                variant = {
                    "path": lib_path,
                    "supportedTriples": platform_info["triple"]
                }
                
                # Only add library metadata for the main skia library
                if lib_info["is_main"]:
                    variant["staticLibraryMetadata"] = {
                        "headerPaths": ["include"],
                        "moduleMapPath": "module.modulemap"
                    }
                
                variants.append(variant)
        
        # Only add libraries that have variants
        if variants:
            artifacts[lib_name] = {
                "version": version,
                "type": "staticLibrary", 
                "variants": variants
            }
    
    info_data = {
        "schemaVersion": "1.0",
        "artifacts": artifacts
    }
    
    info_path = bundle_dir / "info.json"
    with open(info_path, 'w') as f:
        json.dump(info_data, f, indent=4)
    
    print(f"Created {info_path} with {len(artifacts)} library artifacts")


def create_module_map(bundle_dir: Path) -> None:
    """Create the module.modulemap file."""
    
    module_content = """module skia {
    header "include/skia.h"
    link "skia"
    export *
}"""
    
    module_path = bundle_dir / "module.modulemap"
    with open(module_path, 'w') as f:
        f.write(module_content)
    
    print(f"Created {module_path}")


def create_umbrella_header(bundle_dir: Path, temp_dir: Path, version: str) -> None:
    """Create an umbrella header file and copy headers from downloaded packages."""
    
    include_dir = bundle_dir / "include"
    include_dir.mkdir(exist_ok=True)
    
    # Find and copy headers from any downloaded platform (they should be the same)
    headers_copied = False
    
    for platform_dir in temp_dir.iterdir():
        if platform_dir.is_dir():
            source_include_dir = platform_dir / "include"
            if source_include_dir.exists():
                print(f"Copying headers from {source_include_dir}")
                
                # Copy all headers while preserving directory structure
                shutil.copytree(source_include_dir, include_dir, dirs_exist_ok=True)
                headers_copied = True
                break
    
    # Create main umbrella header
    if headers_copied:
        umbrella_content = """// Skia umbrella header
#pragma once

// Core Skia headers
#include "core/SkTypes.h"
#include "core/SkCanvas.h"
#include "core/SkPaint.h"
#include "core/SkPath.h"
#include "core/SkSurface.h"
#include "core/SkImage.h"
#include "core/SkData.h"
#include "core/SkString.h"
#include "core/SkMatrix.h"
#include "core/SkRect.h"
#include "core/SkPoint.h"
#include "core/SkSize.h"
#include "core/SkColor.h"
#include "core/SkColorSpace.h"
#include "core/SkImageInfo.h"
#include "core/SkPixmap.h"
#include "core/SkRefCnt.h"
#include "core/SkShader.h"
#include "core/SkBlendMode.h"
#include "core/SkColorType.h"
#include "core/SkPicture.h"

// GPU headers (optional)
#ifdef SK_GANESH
#include "gpu/GrDirectContext.h"
#endif

// Effects and utilities
#include "effects/SkGradientShader.h"

// SVG support
#ifdef SK_SVG
#include "svg/SkSVGCanvas.h"
#endif
"""
        
        umbrella_path = include_dir / "skia.h"
        with open(umbrella_path, 'w') as f:
            f.write(umbrella_content)
        print(f"Created umbrella header {umbrella_path}")
        
        # Count the number of headers
        header_count = len(list(include_dir.rglob("*.h")))
        print(f"Copied {header_count} header files")
        
    else:
        # Fallback: create a minimal header
        minimal_header = f"""// Skia minimal header - Version {version}
#pragma once

// Include core Skia functionality
// Note: Headers were not found in the downloaded packages
// You may need to include specific Skia headers manually
"""
        umbrella_path = include_dir / "skia.h"
        with open(umbrella_path, 'w') as f:
            f.write(minimal_header)
        print(f"Created minimal header {umbrella_path} (no headers found in packages)")


def copy_libraries(bundle_dir: Path, temp_dir: Path, download_info: Dict) -> Dict:
    """Copy all library files to the artifact bundle and return library info."""
    
    all_libraries = {}
    
    for platform, info in download_info.items():
        platform_dir = bundle_dir / platform
        platform_dir.mkdir(exist_ok=True)
        
        source_dir = temp_dir / platform
        if not source_dir.exists():
            print(f"Warning: Source directory {source_dir} not found for {platform}")
            continue
        
        # Find all library files
        if platform.startswith("windows"):
            lib_files = list(source_dir.rglob("*.lib"))
        else:
            lib_files = list(source_dir.rglob("*.a"))
        
        platform_libraries = []
        
        for source_lib in lib_files:
            # Skip certain files that aren't libraries
            if source_lib.name in ["icudtl.dat"]:
                continue

            suffix = source_lib.suffix
            original_stem = source_lib.stem

            if platform.startswith("windows"):
                # Ensure Windows libraries have a lib prefix in the filename
                if original_stem.lower().startswith("lib"):
                    target_stem = original_stem[3:]
                else:
                    target_stem = original_stem
                target_name = f"{target_stem}{suffix}"
            else:
                target_stem = original_stem
                target_name = source_lib.name

            target_lib = platform_dir / target_name
            shutil.copy2(source_lib, target_lib)
            print(f"Copied {source_lib} to {target_lib}")

            # Determine library name without leading lib prefix for artifact naming
            if target_stem.startswith("lib"):
                display_name = target_stem[3:]
            else:
                display_name = target_stem

            platform_libraries.append({
                "file_name": target_name,
                "lib_name": display_name,
                "is_main": display_name.lower() == "skia"
            })
        
        all_libraries[platform] = platform_libraries
        print(f"Copied {len(platform_libraries)} libraries for {platform}")
    
    return all_libraries


def create_zip_file(bundle_dir: Path, version: str) -> Path:
    """Create a ZIP file of the artifact bundle."""
    
    zip_name = f"skia-{version}.artifactbundle.zip"
    zip_path = bundle_dir.parent / zip_name
    
    print(f"Creating ZIP file: {zip_path}")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in bundle_dir.rglob("*"):
            if file_path.is_file():
                # Create the path in the ZIP relative to the bundle directory
                arc_name = bundle_dir.name / file_path.relative_to(bundle_dir)
                zip_file.write(file_path, arc_name)
                
    # Get file size for reporting
    zip_size = zip_path.stat().st_size
    zip_size_mb = zip_size / (1024 * 1024)
    
    print(f"ZIP file created: {zip_path} ({zip_size_mb:.1f} MB)")
    return zip_path


def main():
    parser = argparse.ArgumentParser(
        description="Build an artifact bundle for pre-compiled Skia binaries"
    )
    parser.add_argument(
        "--version", 
        default="m126-6bfb13368b",
        help="Version of Skia to download (default: m126-6bfb13368b)"
    )
    parser.add_argument(
        "--output",
        default="skia.artifactbundle",
        help="Output directory for the artifact bundle (default: skia.artifactbundle)"
    )
    parser.add_argument(
        "--zip",
        action="store_true",
        help="Create a ZIP file of the artifact bundle"
    )
    
    args = parser.parse_args()
    
    # Setup directories
    temp_dir = Path("temp")
    bundle_dir = Path(args.output)
    
    temp_dir.mkdir(exist_ok=True)
    bundle_dir.mkdir(exist_ok=True)
    
    print(f"Building Skia artifact bundle version {args.version}")
    print(f"Temp directory: {temp_dir}")
    print(f"Output bundle: {bundle_dir}")
    
    # Get download information
    download_info = get_download_info(args.version)
    
    # Download and extract binaries for each platform
    extracted_platforms = {}
    for platform, info in download_info.items():
        extracted_dir = download_and_extract(
            info["url"], 
            temp_dir, 
            platform, 
            info["extract_path"]
        )
        if extracted_dir:
            extracted_platforms[platform] = info
        else:
            print(f"Skipping {platform} due to download/extraction failure")
    
    if not extracted_platforms:
        print("Error: No platforms were successfully downloaded")
        sys.exit(1)
    
    # Create artifact bundle structure
    create_module_map(bundle_dir)
    create_umbrella_header(bundle_dir, temp_dir, args.version)
    all_libraries = copy_libraries(bundle_dir, temp_dir, extracted_platforms)
    create_info_json(bundle_dir, args.version, extracted_platforms, all_libraries)
    
    print(f"\nArtifact bundle created successfully at {bundle_dir}")
    
    # Create ZIP file if requested
    if args.zip:
        zip_path = create_zip_file(bundle_dir, args.version)
        print(f"ZIP file created at {zip_path}")
    else:
        print("Contents:")
        for item in sorted(bundle_dir.rglob("*")):
            if item.is_file():
                print(f"  {item.relative_to(bundle_dir)}")


if __name__ == "__main__":
    main()
