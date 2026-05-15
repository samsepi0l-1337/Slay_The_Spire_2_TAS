# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.24)

project(sts2_tas_hook LANGUAGES CXX)

# Scaffold only: this target documents the Windows x64 passive-only hook canary.
# The repository tests currently assert that the file and policy tokens exist;
# CI is not expected to configure, build, inject, or execute this native DLL.
if(NOT WIN32)
  message(STATUS "sts2_tas_hook is a Windows x64 scaffold; skipping non-Windows build.")
  return()
endif()

if(NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
  message(FATAL_ERROR "sts2_tas_hook is x64-only.")
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(sts2_tas_hook SHARED sts2_tas_hook.cpp)

target_compile_definitions(sts2_tas_hook PRIVATE
  WIN32_LEAN_AND_MEAN
  NOMINMAX
  STS2_TAS_HOOK_PASSIVE_ONLY=1
)

target_compile_options(sts2_tas_hook PRIVATE
  /W4
  /permissive-
)

# Detours is intentionally optional in this scaffold. A later real canary build
# should provide Microsoft Detours and replace the placeholder install path with
# a passive Present hook attach path.
find_path(DETOURS_INCLUDE_DIR detours.h)
find_library(DETOURS_LIBRARY detours)

if(DETOURS_INCLUDE_DIR AND DETOURS_LIBRARY)
  target_compile_definitions(sts2_tas_hook PRIVATE STS2_TAS_HOOK_HAS_DETOURS=1)
  target_include_directories(sts2_tas_hook PRIVATE "${DETOURS_INCLUDE_DIR}")
  target_link_libraries(sts2_tas_hook PRIVATE "${DETOURS_LIBRARY}")
else()
  target_compile_definitions(sts2_tas_hook PRIVATE STS2_TAS_HOOK_HAS_DETOURS=0)
endif()

target_link_libraries(sts2_tas_hook PRIVATE
  d3d11
  dxgi
  user32
)

set_target_properties(sts2_tas_hook PROPERTIES
  OUTPUT_NAME "sts2_tas_hook"
)
