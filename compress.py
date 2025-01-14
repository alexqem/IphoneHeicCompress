import os
from PIL import Image, ImageEnhance
import pillow_heif
from pathlib import Path
import io
from concurrent.futures import ThreadPoolExecutor
import threading

# Global Variables
SHARPNESS_FACTOR = 1.1
VIBRANCE_FACTOR = 1.1
SATURATION_FACTOR = 1.15
MAX_SIDE = 1600
MAX_SIZE_KB = 1024
INPUT_DIR = "./MyHair"
OUTPUT_DIR = "./newHair"
print_lock = threading.Lock()

def safe_print(*args, **kwargs):
    with print_lock:
        print(*args, **kwargs)

def copy_file_metadata(src_path, dst_path):
    """Copy file metadata from source to destination"""
    try:
        # Get source file's stats
        src_stat = os.stat(src_path)
        
        # Copy access and modification times
        os.utime(dst_path, (src_stat.st_atime, src_stat.st_mtime))
        
        # On macOS, use touch command with reference to preserve creation time
        if platform.system() == 'Darwin':  # macOS
            os.system(f"touch -r '{src_path}' '{dst_path}'")
            
    except Exception as e:
        safe_print(f"Warning: Could not copy metadata: {e}")

def resize_image(image):
    if image is None:
        raise ValueError("Image is None in resize_image")
    width, height = image.size
    if max(width, height) > MAX_SIDE:
        ratio = min(MAX_SIDE / width, MAX_SIDE / height)
        return image.resize((int(width * ratio), int(height * ratio)), Image.Resampling.LANCZOS)
    return image

def enhance_image(image):
    if image is None:
        raise ValueError("Image is None in enhance_image")
    try:
        image = ImageEnhance.Sharpness(image).enhance(SHARPNESS_FACTOR)
        image = ImageEnhance.Contrast(image).enhance(VIBRANCE_FACTOR)
        return ImageEnhance.Color(image).enhance(SATURATION_FACTOR)
    except Exception as e:
        safe_print(f"Enhancement error: {e}")
        return image

def process_image(file):
    try:
        safe_print(f"Processing: {file.name}")
        
        # Verify file exists and is readable
        if not file.exists():
            raise FileNotFoundError(f"File not found: {file}")
        
        # Try to open the HEIC file directly with pillow_heif
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
        
        # Process the image
        image = resize_image(image)
        image = enhance_image(image)
        
        # Save the processed image
        output_path = Path(OUTPUT_DIR) / f"{file.stem}.jpg"
        
        # Progressive save with quality reduction until size requirement is met
        quality = 95
        while quality > 30:
            try:
                image.save(output_path, 
                          "JPEG", 
                          quality=quality, 
                          optimize=True, 
                          progressive=True)
                
                # Check if file size meets requirements
                if os.path.getsize(output_path) <= MAX_SIZE_KB * 1024:
                    break
                
                quality -= 5
                
            except Exception as e:
                safe_print(f"Save attempt failed at quality {quality}: {e}")
                quality -= 5
                continue
        
        if quality <= 30:
            safe_print(f"Warning: Could not compress {file.name} to target size while maintaining quality")
        
        # Copy metadata from source to destination
        copy_file_metadata(file, output_path)
        
        safe_print(f"Success: {file.name} → {output_path.name}")
        
    except Exception as e:
        safe_print(f"Error processing {file.name}: {str(e)}")
        import traceback
        safe_print(traceback.format_exc())

def process_images():
    pillow_heif.register_heif_opener()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    if not os.path.exists(INPUT_DIR):
        safe_print(f"Input directory {INPUT_DIR} does not exist!")
        return
    
    files = list(Path(INPUT_DIR).glob("*.HEIC")) + list(Path(INPUT_DIR).glob("*.heic"))
    
    if not files:
        safe_print(f"No HEIC files found in {INPUT_DIR}")
        return
    
    safe_print(f"Found {len(files)} HEIC files. Processing...")
    
    with ThreadPoolExecutor() as executor:
        executor.map(process_image, files)
    
    safe_print("Processing complete.")

if __name__ == "__main__":
    import platform
    process_images()
