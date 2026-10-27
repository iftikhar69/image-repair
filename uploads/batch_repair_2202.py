import os
import cv2
from PIL import Image, ImageFile

# Allow Pillow to open partially corrupted/truncated JPEGs
ImageFile.LOAD_TRUNCATED_IMAGES = True

def process_batch(input_folder, output_folder, error_folder):
    # Ensure directories exist
    os.makedirs(output_folder, exist_ok=True)
    os.makedirs(error_folder, exist_ok=True)

    supported_extensions = ('.jpg', '.jpeg', '.png', '.bmp')
    files = [f for f in os.listdir(input_folder) if f.lower().endswith(supported_extensions)]
    
    total_files = len(files)
    print(f"Found {total_files} images to process...\n" + "="*40)

    success_count = 0
    fail_count = 0

    for idx, filename in enumerate(files, start=1):
        input_path = os.path.join(input_folder, filename)
        output_path = os.path.join(output_folder, filename)
        error_path = os.path.join(error_folder, filename)

        repaired = False

        # Attempt 1: Pillow truncated scanline recovery
        try:
            with Image.open(input_path) as img:
                img = img.convert("RGB")
                img.save(output_path, "JPEG", quality=95, optimize=True)
                repaired = True
        except Exception:
            pass

        # Attempt 2: OpenCV fallback if Pillow failed or file matrix is damaged
        if not repaired:
            try:
                matrix = cv2.imread(input_path, cv2.IMREAD_COLOR)
                if matrix is not None:
                    cv2.imwrite(output_path, matrix, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
                    repaired = True
            except Exception:
                pass

        if repaired:
            success_count += 1
            print(f"[{idx}/{total_files}] REPAIRED: {filename}")
        else:
            fail_count += 1
            # Move completely unrecoverable files to error folder
            try:
                with open(input_path, 'rb') as src, open(error_path, 'wb') as dst:
                    dst.write(src.read())
            except Exception:
                pass
            print(f"[{idx}/{total_files}] FAILED: {filename} (Moved to error folder)")

    print("="*40)
    print(f"Batch Processing Complete!")
    print(f"Successfully Processed: {success_count}")
    print(f"Failed / Completely Unreadable: {fail_count}")

if __name__ == "__main__":
    # Define folder paths relative to the script location
    INPUT_DIR = "./corrupted_images"
    OUTPUT_DIR = "./repaired_images"
    FAILED_DIR = "./unrepairable_images"

    process_batch(INPUT_DIR, OUTPUT_DIR, FAILED_DIR)
