# Camera Tethering R&D - Getting Photos from Camera to Backend

**Goal:** Automatically transfer photos from camera to backend storage for WedFind AI processing.

---

## Methods Summary

| Method | Connection | Reliability | Speed | Complexity | Best For |
|--------|------------|-------------|-------|------------|----------|
| **USB Tethering** | USB-C cable | ⭐⭐⭐⭐⭐ | Fast | Low | Studio setup |
| **WiFi Tethering** | WiFi network | ⭐⭐⭐ | Medium | Low | On-location |
| **SD Card + Auto-import** | Card reader | ⭐⭐⭐⭐⭐ | Fast | Very Low | High volume |
| **Manufacturer SDK** | USB/WiFi | ⭐⭐⭐⭐ | Fast | High | Custom control |

---

## 1. USB Tethering (Recommended for Studio)

**How it works:** Camera connected via USB-C, computer runs tethering software that auto-downloads photos to a watched folder.

**Software Options:**

| Software | Cost | Platform | Notes |
|----------|------|----------|-------|
| [Digicam Control 2](https://digicamcontrol.com/) | Free | Windows | Open source, full camera control |
| [Capture One](https://www.captureone.com/) | Paid | Win/Mac | Pro-grade, industry standard |
| Canon EOS Utility | Free | Win/Mac | Canon cameras only |
| Fujifilm Wireless Tethering | Free | Win/Mac | Fuji GFX series |

**Integration with WedFind:**
1. Tethering software saves to folder: `D:\WedFind\Incoming\EventName\`
2. Existing `folder_watcher.py` monitors that folder
3. Auto-uploads to S3 when photos appear

---

## 2. WiFi Tethering

**How it works:** Camera creates WiFi hotspot, computer connects, photos transfer wirelessly.

**Options:**
- [Tether Tools Air Direct](https://tethertools.com/products/air-direct-usb-to-wireless-tethering-adapter) - Hardware adapter for cameras without WiFi
- Canon EOS Utility (WiFi mode)
- Fujifilm Wireless Tethering
- OM Cameras Wireless Tether (Microsoft Store)

**Pros:** No cables, freedom of movement
**Cons:** Slower, can be unreliable, battery drain

---

## 3. SD Card Auto-Import (Simplest)

**How it works:** Pop SD card into reader, OS auto-imports to watched folder.

**Windows:** "Photos" app auto-import, or script watching `E:\DCIM\`
**Mac:** Image Capture with auto-import

**Best for:** High-volume shooting where tethering slows down capture

---

## 4. Manufacturer SDKs (Programmatic Control)

For direct backend integration without external software:

### Sony Camera Remote SDK
- [Official SDK](https://support.d-imaging.sony.co.jp/app/sdk/en/index.html)
- Remote control, live view, image transfer
- Python bindings available
- Most developer-friendly

### Canon EOS Digital SDK
- [Overview](https://en.canon-me.com/pro/stories/eos-digital-sdk-explained/)
- Tethered shooting control
- Compatible with EOS Utility

### Nikon SDK
- Available through Nikon developer program
- Similar capabilities

**Note:** Building custom SDK integration is complex. Usually better to use existing tethering software + folder watcher.

---

## 5. Python Libraries

### gphoto2
Open-source library supporting 100+ cameras.

**Install:**
```bash
# Linux
sudo apt-get install libgphoto2-2-dev gphoto2
pip install gphoto2-cffi

# macOS
brew install gphoto2
pip install gphoto2-cffi

# Windows - more complex, needs precompiled binaries
```

**Usage:**
```python
from gphoto2cffi import Camera

cam = Camera()
cam.init()
# Capture and download
cam.capture('output.jpg')
cam.exit()
```

**Resources:**
- [gphoto2-cffi docs](https://gphoto2-cffi.readthedocs.io/)
- [DIY Tethering with gPhoto2](https://www.youtube.com/watch?v=o9KtXqZZBrc) (video)
- [Howto: Tethered photo capture on Linux](https://mike42.me/blog/2015-01-howto-tethered-photo-capture-on-linux)

**Pros:** Free, cross-platform, many cameras
**Cons:** Linux support best, Windows tricky

---

## Recommended Approach for WedFind AI

**Option A - Simple (Start Here):**
1. Use existing tethering software (Digicam Control / Capture One)
2. Configure save folder to watched directory
3. Existing `folder_watcher.py` handles upload

**Option B - Custom Integration:**
1. Integrate gphoto2-cffi into backend
2. Add camera connection management UI
3. Direct capture → S3 pipeline

**Option C - Hybrid:**
1. Folder watcher as base (already exists)
2. Add camera detection for auto-configuration
3. Support both tethered software AND direct SDK capture

---

## Next Steps

1. **Test existing folder watcher:**
   - Create test folder
   - Add test image
   - Verify upload to S3 works

2. **Choose camera hardware:**
   - What cameras will photographers use?
   - Check SDK/tethering support

3. **Test tethering workflow:**
   - Try Digicam Control (free, Windows)
   - Point to test folder
   - Capture test shot
   - Verify full pipeline

---

## Sources

- [Evoto AI Tethering Software](https://www.evoto.ai/features/tethering-shooting-software)
- [Sony Camera Remote SDK](https://support.d-imaging.sony.co.jp/app/sdk/en/index.html)
- [Canon EOS SDK Explained](https://en.canon-me.com/pro/stories/eos-digital-sdk-explained/)
- [gphoto2-cffi Documentation](https://gphoto2-cffi.readthedocs.io/)
- [DIY Tethering Tutorial](https://www.youtube.com/watch?v=o9KtXqZZBrc)
- [Howto: Tethered photo capture on Linux](https://mike42.me/blog/2015-01-howto-tethered-photo-capture-on-linux)
- [Raspberry Pi DSLR Control](https://maskaravivek.medium.com/how-to-control-and-capture-images-from-dslr-using-raspberry-pi-cfc0cf2d5e85)
