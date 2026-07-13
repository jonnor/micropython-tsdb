

## Storage budgeting

8 MB FLASH total

- MicroPython ESP32 2 MB with .py/.mpy libraries
- Web assets. Incl Plotly, MicroPython.wasm. 2 MB 
- Data storage internal. 4 MB

0.125 ms soundlevels - 4 bytes per entry. 
*8*60*60*24 / 1e6 = 2.76 MB per day

1 minute soundlevels, 3 metrics, 4 bytes each.
3*4*60*24*30 / 1e6 = 0.5184 MB per 30 days

50 Hz accelerometer data - 6 bytes for 3 channels.
3*2*50*3600*23 / 1e6 = 24.84 MB per 24 hours
Want to compress by a factor of 10x. Sounds doable.

Effects of Sampling Frequency on Human Activity Recognition with Machine Learning Aiming at Clinical Applications
https://pmc.ncbi.nlm.nih.gov/articles/PMC12196717/
Reducing the sampling frequency to 10 Hz did not significantly affect the recognition accuracy for either location. 

20-25 Hz would be sufficient.

! would want gyro data also.
Or orientation and linear acceleration separated out.
! requires deciding the gyro mixing ratio


### Tests

- Load 1 year of daily-paritioned data, with 1 minute resolution
- Load 1 day of hour-partitioned data, with 1 second resolution
- Load 1 hour of 20hz raw data
- Appending 20hz raw data, in small chunks. With auto-compaction

Key requirement: at no time should any process be blocking for more than 100 ms. 

## HTTP multiple requests

What happens if one browser/client makes multiple requests?
With MicroDot.



## HTTP testing from RAM

Using ESP32 pico in M5StickC PLUS 2 over WiFi

$ for chunk in 1024 2048 4096 8192 16384 32768 65536; do curl -s "http://192.168.87.152:5000/stream?chunk=$chunk" -o /dev/null -w "chunk=$chunk: HTTP %{http_code}, Size: %{size_download} bytes, Time: %{time_total}s, Speed: %{speed_download} bytes/s\n" --max-time 60; done
chunk=1024: HTTP 200, Size: 524288 bytes, Time: 3.901785s, Speed: 134371 bytes/s
chunk=2048: HTTP 200, Size: 524288 bytes, Time: 2.629534s, Speed: 199384 bytes/s
chunk=4096: HTTP 200, Size: 524288 bytes, Time: 1.776227s, Speed: 295169 bytes/s
chunk=8192: HTTP 200, Size: 524288 bytes, Time: 2.624618s, Speed: 199757 bytes/s
chunk=16384: HTTP 200, Size: 524288 bytes, Time: 3.488393s, Speed: 150294 bytes/s
chunk=32768: HTTP 200, Size: 524288 bytes, Time: 5.452071s, Speed: 96163 bytes/s
chunk=65536: HTTP 200, Size: 524288 bytes, Time: 4.939647s, Speed: 106138 bytes/s
Now streaming 512KB. 4KB chunk wins at 295 KB/s, then 2KB at 199 KB/s. Performance degrades significantly with larger chunk sizes.

Would take 16 seconds for 4 MB of data.
Not fast enough to be done in once go.
Needs to be background and iterative.

## HTTP testing from disk/FLASH

First version

Results:
| Chunk | Time | Speed |
|-------|------|-------|
| 1024 | 8.18s | 64 KB/s |
| 2048 | 5.31s | 99 KB/s |
| 4096 | 3.64s | 144 KB/s |
| 8192 | 4.35s | 121 KB/s |
| 16384 | 9.07s | 58 KB/s |
| 32768 | 7.54s | 70 KB/s |
| 65536 | 8.30s | 63 KB/s |

accidentially read continiously for as long as request open

chunk=1024: Size: 3309568 bytes, Time: 30.000507s, Speed: 110317 bytes/s
chunk=4096: Size: 9334784 bytes, Time: 30.000009s, Speed: 311159 bytes/s
chunk=8192: Size: 4114176 bytes, Time: 30.001165s, Speed: 137133 bytes/s
chunk=16384: Size: 2172032 bytes, Time: 30.000515s, Speed: 72399 bytes/s

With fixed termination.

File-Stream Benchmark Results:
| Chunk | Size | Time | Speed |
|-------|------|------|-------|
| 1024 | 512KB | 6.06s | 87 KB/s |
| 2048 | 512KB | 4.11s | 127 KB/s |
| 4096 | 512KB | 3.23s | 162 KB/s |
| 8192 | 512KB | 3.49s | 150 KB/s |
| 16384 | 512KB | 6.41s | 82 KB/s |
| 32768 | 512KB | 9.36s | 56 KB/s |

Seems like 150 kB/s is best we can do for now.


There are some benchmarks for LittleFS on ESP32 at
https://components.espressif.com/components/joltwallet/littlefs/versions/1.20.4/readme

```
Reading 5 88KB files
LittleFS (cache=512 default):   5,874,931 us
LittleFS (cache=4096):          5,731,385 us
```
That is around 88kB per second.

