# iPhone Photo Compressor

This repository contains a Python script to compress iPhone photos from HEIC format to highly optimized JPEG format. The script uses multithreading to process multiple images efficiently.

## Features

- Converts HEIC images to JPEG.
- Resizes images to a maximum side length of 1600 pixels.
- Adjusts sharpness, vibrance, and saturation.
- Compresses images to a maximum size of 1MB.
- Uses multithreading for faster processing.

## Requirements

- Python 3.6+
- Pillow
- Pillow-HEIF
- Pieexif
```bash
pip install pillow pillow-heif pieexif
```

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/alexqem/IphoneHeicCompress.git
   cd IphoneHeicCompress
