# Builds the public site into docs/ (GitHub Pages serves this folder) and the private preview page.
#   powershell -ExecutionPolicy Bypass -File build.ps1                      # public site uses the working name
#   powershell -ExecutionPolicy Bypass -File build.ps1 -Name "Aggieland Shade Walk"   # only after TAMU licensing approves
param(
  [string]$Name = "Shade Walk CS",
  [string]$ShortName = "Shade Walk"
)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$enc = New-Object Text.UTF8Encoding $false
function Read-Text($p) { [IO.File]::ReadAllText((Join-Path $root $p), [Text.Encoding]::UTF8) }
function Write-Text($p, $s) { [IO.File]::WriteAllText((Join-Path $root $p), $s, $enc) }

$tpl = Read-Text "src\template.html"
$page = $tpl.Replace('/*CAMPUS*/null', (Read-Text "data\campus.json")).Replace('/*BUS*/null', (Read-Text "data\bus.json")).Replace('/*OFF*/null', (Read-Text "data\offcampus.json"))
$version = (Get-Date).ToString("yyyyMMddHHmm")

# ---- public site (docs/) ----
$head = @"
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Find the shadiest walk across the Texas A&amp;M campus and the shady side of the campus bus, for any date and time. Free, no sign-in.">
<meta name="theme-color" content="#1C1E21">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="$ShortName">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" type="image/png" sizes="192x192" href="icons/icon-192.png">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<style>*,*::before,*::after{box-sizing:border-box}:root{color-scheme:light}body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>
<script>window.__SITE__ = true;</script>
"@
$site = $page.Replace('<!--HEAD-->', $head).Replace('__APP_NAME__', $Name)
# title, fonts and styles stay in <head>; the body starts at the app container
$bodyAt = $site.IndexOf('<div class="app">')
$site = $site.Substring(0, $bodyAt) + "</head>`n<body>`n" + $site.Substring($bodyAt) + "`n</body>`n</html>`n"
Write-Text "docs\index.html" $site

$manifest = @"
{
  "name": "$Name",
  "short_name": "$ShortName",
  "description": "Shadiest walking routes and bus seats on the Texas A&M campus, for any date and time.",
  "start_url": "./",
  "scope": "./",
  "display": "standalone",
  "background_color": "#1C1E21",
  "theme_color": "#1C1E21",
  "icons": [
    { "src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png" },
    { "src": "icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ]
}
"@
Write-Text "docs\manifest.webmanifest" $manifest

$sw = @"
// Offline support: the page and its data ship in one file, so caching index.html is enough to work without signal.
const CACHE = "shade-$version";
const CORE = ["./", "index.html", "manifest.webmanifest", "icons/icon-192.png", "icons/icon-512.png", "icons/apple-touch-icon.png"];
self.addEventListener("install", e => e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  const u = new URL(e.request.url);
  if (u.origin === location.origin) {
    if (e.request.mode === "navigate") {  // network first so new versions show up, cache when offline
      e.respondWith(fetch(e.request).then(r => { const copy = r.clone(); caches.open(CACHE).then(c => c.put("index.html", copy)); return r; })
        .catch(() => caches.match("index.html")));
      return;
    }
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
  } else if (u.hostname === "fonts.googleapis.com" || u.hostname === "fonts.gstatic.com") {
    e.respondWith(caches.open(CACHE).then(c => c.match(e.request).then(r => r || fetch(e.request).then(res => { c.put(e.request, res.clone()); return res; }))));
  }
});
"@
Write-Text "docs\sw.js" $sw
Write-Text "docs\.nojekyll" ""

# ---- private preview page (published as a Claude artifact; not public) ----
Write-Text "aggie-shade-walk.html" ($page.Replace('<!--HEAD-->', '').Replace('__APP_NAME__', 'Aggieland Shade Walk'))

"Built docs/ as '$Name' (version $version), $([math]::Round($site.Length/1MB,2)) MB"
