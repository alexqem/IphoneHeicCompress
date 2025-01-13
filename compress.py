import os
from PIL import Image, ImageEnhance
import pillow_heif
from pathlib import Path
import io
import concurrent.futures
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
    """Thread-safe printing"""
    with print_lock:
        print(*args, **kwargs)

def resize_image(image, max_side=MAX_SIDE):
    """Resize image if any dimension exceeds max_side"""
    width, height = image.size
    if width > max_side or height > max_side:
        # Calculate new dimensions maintaining aspect ratio
        ratio = min(max_side/width, max_side/height)
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    return image

def compress_image(image, max_size_kb=MAX_SIZE_KB):
    """
    Iteratively compress image until target size is reached while maintaining quality
    """
    quality = 95
    min_quality = 30
    target_size = max_size_kb * 1024
    
    webp_buffer = io.BytesIO()
    image.save(webp_buffer, format="WEBP", quality=quality)
    
    webp_buffer.seek(0)
    image = Image.open(webp_buffer)
    
    while quality > min_quality:
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality, optimize=True)
        if buffer.tell() <= target_size:
            buffer.seek(0)
            return Image.open(buffer)
        quality -= 5
    
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=min_quality, optimize=True)
    buffer.seek(0)
    return Image.open(buffer)

def process_single_image(file, output_dir, max_size_kb=MAX_SIZE_KB, sharpness_factor=SHARPNESS_FACTOR, max_side=MAX_SIDE):
    """Process a single image file"""
    try:
        safe_print(f"Processing: {file.name}")
        
        # Open HEIC image
        image = Image.open(file)
        
        # Convert to RGB
        image = image.convert('RGB')
        
        # Resize if needed
        image = resize_image(image, max_side)
        
        # Adjust sharpness
        enhancer = ImageEnhance.Sharpness(image)
        sharpened_image = enhancer.enhance(sharpness_factor)
        
        # Increase vibrance (through contrast)
        enhancer = ImageEnhance.Contrast(sharpened_image)
        vibrant_image = enhancer.enhance(VIBRANCE_FACTOR)  # +10%
        
        # Increase saturation
        enhancer = ImageEnhance.Color(vibrant_image)
        saturated_image = enhancer.enhance(SATURATION_FACTOR)  # +15%
        
        # Update the image for compression (replace this line)
        compressed_image = compress_image(saturated_image, max_size_kb)

        
        # Save as JPG
        jpg_path = Path(output_dir) / f"{file.stem}.jpg"
        compressed_image.save(
            jpg_path,
            'JPEG',
            optimize=True,
            progressive=True
        )
        
        # Get original and new file sizes
        original_size = os.path.getsize(file)
        new_size = os.path.getsize(jpg_path)
        compression_ratio = (1 - new_size/original_size) * 100
        
        safe_print(f"Success: {file.name}")
        safe_print(f"Size reduction: {original_size/1024/1024:.1f}MB → {new_size/1024/1024:.1f}MB")
        safe_print(f"Compression ratio: {compression_ratio:.1f}%")
        
        return True
        
    except Exception as e:
        safe_print(f"Error processing {file.name}: {str(e)}")
        return False

def process_images(input_dir=INPUT_DIR, output_dir=OUTPUT_DIR, max_size_kb=MAX_SIZE_KB, 
                  sharpness_factor=SHARPNESS_FACTOR, max_side=MAX_SIDE):
    """
    Convert HEIC images to highly optimized JPG with multithreading
    """
    # Convert to absolute paths
    input_dir = os.path.abspath(input_dir)
    output_dir = os.path.abspath(output_dir)
    
    safe_print(f"Input directory: {input_dir}")
    safe_print(f"Output directory: {output_dir}")
    
    # Verify input directory exists
    if not os.path.exists(input_dir):
        safe_print(f"Error: Input directory '{input_dir}' does not exist!")
        return
    
    # Register HEIF opener
    pillow_heif.register_heif_opener()
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Find all HEIC files (case insensitive)
    heic_files = []
    for ext in ['*.HEIC', '*.heic']:
        heic_files.extend(Path(input_dir).glob(ext))
    
    if not heic_files:
        safe_print(f"No HEIC files found in {input_dir}")
        return
    
    safe_print(f"Found {len(heic_files)} HEIC files")
    
    # Process images in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(
                process_single_image, 
                file, 
                output_dir, 
                max_size_kb, 
                sharpness_factor,
                max_side
            )
            for file in heic_files
        ]
        
        concurrent.futures.wait(futures)
    
    # Count successes
    successes = sum(1 for future in futures if future.result())
    safe_print(f"\nProcessing complete: {successes}/{len(heic_files)} images converted successfully")

if __name__ == "__main__":
    # Use default directories and settings
    process_images()
