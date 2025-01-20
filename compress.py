import os
from PIL import Image, ImageEnhance
import pillow_heif
from pathlib import Path
import io
from concurrent.futures import ThreadPoolExecutor
import threading
import piexif
from datetime import datetime
from typing import Optional

# Global Variables
SHARPNESS_FACTOR = 1.1
VIBRANCE_FACTOR = 1.1
SATURATION_FACTOR = 1.15
MAX_SIDE = 1900
MAX_SIZE_KB = 1024
INPUT_DIR = "./old"
OUTPUT_DIR = "./new"
print_lock = threading.Lock()

def safe_print(*args, **kwargs) -> None:
    with print_lock:
        print(*args, **kwargs)

def extract_metadata(image: Image.Image, src_path: Path) -> Optional[bytes]:
    """Extract EXIF and other metadata from source image"""
    try:
        # Try to get EXIF data from the image
        exif_dict = None
        
        # First try getting EXIF from the image object
        if hasattr(image, '_getexif'):
            exif_data = image._getexif()
            if exif_data:
                # Convert the EXIF data to a format we can work with
                exif_dict = piexif.load(image.info.get('exif', b''))
                return piexif.dump(exif_dict)
        
        # If no EXIF data found, create a basic EXIF structure with datetime
        stat = os.stat(src_path)
        try:
            # macOS specific - use birth time (creation time)
            timestamp = stat.st_birthtime
        except AttributeError:
            # Fallback to modification time if birth time is not available
            timestamp = stat.st_mtime
        
        # Create datetime string in EXIF format
        date_str = datetime.fromtimestamp(timestamp).strftime("%Y:%m:%d %H:%M:%S")
        
        # Create basic EXIF dictionary
        exif_dict = {
            "0th": {
                piexif.ImageIFD.Make: "Unknown".encode('utf-8'),
                piexif.ImageIFD.Model: "Unknown".encode('utf-8'),
                piexif.ImageIFD.DateTime: date_str.encode('utf-8')
            },
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: date_str.encode('utf-8'),
                piexif.ExifIFD.DateTimeDigitized: date_str.encode('utf-8')
            },
            "GPS": {},
            "1st": {},
            "thumbnail": None
        }
        return piexif.dump(exif_dict)
            
    except Exception as e:
        safe_print(f"Warning: Could not extract metadata: {e}")
        return None

def resize_image(image: Image.Image) -> Image.Image:
    """Resize image while maintaining aspect ratio"""
    if image is None:
        raise ValueError("Image is None in resize_image")
    width, height = image.size
    if max(width, height) > MAX_SIDE:
        ratio = min(MAX_SIDE / width, MAX_SIDE / height)
        return image.resize((int(width * ratio), int(height * ratio)), Image.Resampling.LANCZOS)
    return image

def enhance_image(image: Image.Image) -> Image.Image:
    """Apply enhancement filters to the image"""
    if image is None:
        raise ValueError("Image is None in enhance_image")
    try:
        image = ImageEnhance.Sharpness(image).enhance(SHARPNESS_FACTOR)
        image = ImageEnhance.Contrast(image).enhance(VIBRANCE_FACTOR)
        return ImageEnhance.Color(image).enhance(SATURATION_FACTOR)
    except Exception as e:
        safe_print(f"Enhancement error: {e}")
        return image

def process_image(file: Path) -> None:
    """Process a single image file"""
    try:
        safe_print(f"Processing: {file.name}")

        # Verify file exists and is readable
        if not file.exists():
            raise FileNotFoundError(f"File not found: {file}")
        
        # Try to open the HEIC file with pillow_heif
        try:
            heif_file = pillow_heif.read_heif(str(file))
            image = Image.frombytes(
                heif_file.mode,
                heif_file.size,
                heif_file.data,
                "raw",
                heif_file.mode,
                heif_file.stride,
            )
        except Exception as e:
            safe_print(f"HEIF reading failed, trying PIL: {e}")
            # Fallback to PIL
            image = Image.open(file)
        
        if image is None:
            raise ValueError("Unable to open image, file may be corrupted.")
        
        # Convert to RGB early to ensure consistent color space
        image = image.convert('RGB')
        
        # Extract metadata before processing
        exif_data = extract_metadata(image, file)
        
        # Process the image
        image = resize_image(image)
        image = enhance_image(image)
        
        # Prepare output path
        output_path = Path(OUTPUT_DIR) / f"{file.stem}.jpg"
        
        # Progressive save with quality reduction until size requirement is met
        quality = 95
        while quality > 30:
            try:
                # Create a buffer to check file size before saving
                buffer = io.BytesIO()
                image.save(buffer, 
                          format="JPEG", 
                          quality=quality, 
                          optimize=True, 
                          progressive=True,
                          exif=exif_data)
                
                # Check if size meets requirements
                if buffer.tell() <= MAX_SIZE_KB * 1024:
                    # If size is good, save the actual file
                    with open(output_path, 'wb') as f:
                        f.write(buffer.getvalue())
                    break
                
                quality -= 5
                
            except Exception as e:
                safe_print(f"Save attempt failed at quality {quality}: {e}")
                quality -= 5
                continue
        
        if quality <= 30:
            safe_print(f"Warning: Could not compress {file.name} to target size while maintaining quality")
        
        # Use macOS specific touch command to preserve metadata
        os.system(f"touch -r '{file}' '{output_path}'")
        
        safe_print(f"Success: {file.name} → {output_path.name}")
        
    except Exception as e:
        safe_print(f"Error processing {file.name}: {str(e)}")
        import traceback
        safe_print(traceback.format_exc())

def process_images() -> None:
    """Process all HEIC images in the input directory"""
    pillow_heif.register_heif_opener()
    
    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.exists(INPUT_DIR):
        safe_print(f"Input directory {INPUT_DIR} does not exist!")
        return

    # Use Path.glob with a case-insensitive pattern for macOS
    files = list(Path(INPUT_DIR).glob("*.HEIC")) + list(Path(INPUT_DIR).glob("*.heic"))

    if not files:
        safe_print(f"No HEIC files found in {INPUT_DIR}")
        return

    safe_print(f"Found {len(files)} HEIC files. Processing...")

    # Use ThreadPoolExecutor for parallel processing
    with ThreadPoolExecutor() as executor:
        executor.map(process_image, files)

    safe_print("Processing complete.")

if __name__ == "__main__":
    process_images()
