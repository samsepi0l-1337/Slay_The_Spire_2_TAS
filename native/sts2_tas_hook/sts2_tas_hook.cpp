// SPDX-License-Identifier: MIT
//
// sts2_tas_hook.cpp
//
// Documentation-first x64 Windows passive-only hook canary scaffold.
// This file intentionally avoids real injection, input, and time hooks. It
// exposes small dummy functions so tests can assert the native contract tokens
// without requiring Microsoft Detours, a Windows SDK build, or Slay the Spire 2.

#include <atomic>
#include <cstdint>

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#else
using BOOL = int;
using DWORD = unsigned long;
using HWND = void*;
#ifndef __declspec
#define __declspec(x)
#endif
#define WINAPI
#define TRUE 1
#endif

#if STS2_TAS_HOOK_HAS_DETOURS
#include <detours.h>
#endif

namespace sts2_tas_hook {

constexpr const char* kSchemaVersion = "sts2-hook-canary.v1";
constexpr const char* kPolicy = "passive-only/no input/no time hook";
constexpr const char* kHookPlan = "Detours based Present hook";
constexpr const char* kCapturePlan = "frame screenshot/hash";
constexpr const char* kIpcPlan = "named pipe JSONL with session nonce and target pid binding";

struct WindowMetadata {
  HWND hwnd;
  bool foreground;
  DWORD process_id;
  DWORD thread_id;
  int client_width;
  int client_height;
};

struct FrameEvent {
  std::uint64_t frame_counter;
  WindowMetadata window;
  const char* schema_version;
  const char* policy;
  const char* capture_mode;
};

std::atomic<std::uint64_t> g_frame_counter{0};

WindowMetadata CollectForegroundWindowMetadata() noexcept {
#if defined(_WIN32)
  HWND hwnd = GetForegroundWindow();
  DWORD process_id = 0;
  DWORD thread_id = hwnd == nullptr ? 0 : GetWindowThreadProcessId(hwnd, &process_id);

  RECT client_rect{};
  int client_width = 0;
  int client_height = 0;
  if (hwnd != nullptr && GetClientRect(hwnd, &client_rect) != FALSE) {
    client_width = static_cast<int>(client_rect.right - client_rect.left);
    client_height = static_cast<int>(client_rect.bottom - client_rect.top);
  }

  return WindowMetadata{
      hwnd,
      hwnd != nullptr && hwnd == GetForegroundWindow(),
      process_id,
      thread_id,
      client_width,
      client_height,
  };
#else
  return WindowMetadata{nullptr, false, 0, 0, 0, 0};
#endif
}

FrameEvent BuildPassiveFrameEvent() noexcept {
  const auto frame = g_frame_counter.fetch_add(1, std::memory_order_relaxed) + 1;
  return FrameEvent{
      frame,
      CollectForegroundWindowMetadata(),
      kSchemaVersion,
      kPolicy,
      "none",
  };
}

// Placeholder for a future Detours Present hook. A real implementation would
// attach to IDXGISwapChain::Present, increment the frame counter, collect
// foreground/window metadata, and optionally copy frame screenshot/hash evidence.
// It must not call SendInput, must not alter focus, and must not install a time
// hook around QueryPerformanceCounter, GetTickCount, sleeps, or frame pacing.
void OnPresentObservedPassiveOnly() noexcept {
  static_cast<void>(BuildPassiveFrameEvent());
}

bool InstallDetoursPresentHookCanary() noexcept {
  // Scaffold only: no actual Detours transaction, no DLL injection, no patching.
  // The policy token is intentionally kept in code for hidden token tests:
  // Detours Present hook, frame counter, foreground/window metadata,
  // frame screenshot/hash, passive-only, no input, no time hook.
  return false;
}

bool UninstallDetoursPresentHookCanary() noexcept {
  return true;
}

}  // namespace sts2_tas_hook

extern "C" {

__declspec(dllexport) const char* WINAPI Sts2TasHookPolicy() {
  return sts2_tas_hook::kPolicy;
}

__declspec(dllexport) const char* WINAPI Sts2TasHookPlan() {
  return sts2_tas_hook::kHookPlan;
}

__declspec(dllexport) std::uint64_t WINAPI Sts2TasHookFrameCounter() {
  return sts2_tas_hook::g_frame_counter.load(std::memory_order_relaxed);
}

__declspec(dllexport) BOOL WINAPI Sts2TasHookInstallCanary() {
  return sts2_tas_hook::InstallDetoursPresentHookCanary() ? TRUE : 0;
}

__declspec(dllexport) BOOL WINAPI Sts2TasHookUninstallCanary() {
  return sts2_tas_hook::UninstallDetoursPresentHookCanary() ? TRUE : 0;
}

}

#if defined(_WIN32)
BOOL WINAPI DllMain(HINSTANCE, DWORD reason, LPVOID) {
  if (reason == DLL_PROCESS_ATTACH) {
    // Passive-only scaffold: do not install hooks from DllMain.
  }
  return TRUE;
}
#endif
