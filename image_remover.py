import os
import base64
import json
import argparse
import logging
from pathlib import Path
from PIL import Image
from openai import OpenAI
from dotenv import load_dotenv
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Constants
BASE_DIR = Path("room_styles")
API_BATCH_SIZE = 10  # Process this many images before pausing to avoid rate limits
API_BATCH_DELAY = 3  # Seconds to wait between batches

def encode_image(image_path):
    """Encode image to base64 for API submission"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"Error encoding image {image_path}: {e}")
        return None

def evaluate_image(client, image_path, encoded_image=None):
    """
    Evaluate if an image is a good picture of a room relevant to interior design
    
    Args:
        client: OpenAI client
        image_path: Path to the image
        encoded_image: Optional pre-encoded image data
        
    Returns:
        tuple: (is_good_image, reason)
    """
    if encoded_image is None:
        encoded_image = encode_image(image_path)
        
    if not encoded_image:
        return False, "Failed to encode image"
    
    try:
        # Prepare system message
        system_message = """You are an expert interior designer evaluating images for an interior design AI assistant.
Your task is to determine if an image is a high-quality, relevant interior design reference image.

Evaluate the image on these criteria:
1. Does it clearly show a room interior?
2. Is it relevant to interior design (shows furniture, decor, layout)?
3. Is it high quality enough to be useful as a reference?
4. Does it appear to be a professionally designed space?

Reply with ONLY ONE of these values:
- "YES" - If the image is a good, relevant interior design reference
- "NO" - If the image is not relevant, unclear, or too low quality
"""

        # Prepare the messages
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": [
                {
                    "type": "text", 
                    "text": "Evaluate if this image is a good, relevant interior design reference picture. Answer with ONLY 'YES' or 'NO'."
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{encoded_image}"
                    }
                }
            ]}
        ]
        
        # Make the API call with simple content
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=50,
            temperature=0.1,  # Low temperature for consistent evaluation
        )
        
        # Get the response text
        response_text = response.choices[0].message.content.strip().upper()
        
        # Get more detailed explanation with a follow-up
        if "YES" in response_text:
            is_good = True
            reason = "Good quality interior design image"
        elif "NO" in response_text:
            is_good = False
            # Get a reason for the rejection
            messages.append({
                "role": "assistant", 
                "content": response_text
            })
            messages.append({
                "role": "user", 
                "content": "Why is this image not suitable? Give a brief reason in one sentence."
            })
            
            detail_response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=100,
            )
            reason = detail_response.choices[0].message.content.strip()
        else:
            # If the response isn't a clear YES or NO, assume it's not good
            is_good = False
            reason = f"Unclear evaluation: {response_text}"
        
        return is_good, reason
        
    except Exception as e:
        logger.error(f"Error evaluating image with API: {e}")
        return False, f"API error: {str(e)}"

def process_directories(dry_run=True, limit=None):
    """
    Process all image directories and evaluate images
    
    Args:
        dry_run: If True, don't actually delete images
        limit: Maximum number of images to process (for testing)
    """
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OpenAI API key not found in environment variables")
        return
        
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    
    # Statistics
    stats = {
        "total_processed": 0,
        "kept": 0,
        "removed": 0,
        "errors": 0,
        "by_style": {}
    }
    
    # Create results directory for logs
    results_dir = Path("image_evaluation_results")
    results_dir.mkdir(exist_ok=True)
    
    # Get all style directories
    if not BASE_DIR.exists():
        logger.error(f"Base directory {BASE_DIR} not found")
        return
        
    style_dirs = [d for d in BASE_DIR.iterdir() if d.is_dir()]
    logger.info(f"Found {len(style_dirs)} style directories")
    
    # Process each style directory
    for style_dir in style_dirs:
        style_name = style_dir.name
        logger.info(f"Processing style: {style_name}")
        
        # Initialize stats for this style
        stats["by_style"][style_name] = {
            "total": 0,
            "kept": 0,
            "removed": 0,
            "errors": 0
        }
        
        # Get all image files
        image_files = [f for f in style_dir.glob("*.jpg")] + \
                      [f for f in style_dir.glob("*.jpeg")] + \
                      [f for f in style_dir.glob("*.png")]
        
        # Skip metadata files
        image_files = [f for f in image_files if not f.name.endswith(".txt")]
        
        logger.info(f"Found {len(image_files)} images in {style_name}")
        
        # Limit the number of images to process if specified
        if limit and stats["total_processed"] + len(image_files) > limit:
            image_files = image_files[:limit - stats["total_processed"]]
            logger.info(f"Limited to {len(image_files)} images due to specified limit")
        
        # Process images in batches to avoid rate limits
        for i, image_file in enumerate(image_files):
            # Update stats
            stats["total_processed"] += 1
            stats["by_style"][style_name]["total"] += 1
            
            logger.info(f"Processing image {i+1}/{len(image_files)}: {image_file.name}")
            
            # Pause between batches to avoid rate limits
            if i > 0 and i % API_BATCH_SIZE == 0:
                logger.info(f"Pausing for {API_BATCH_DELAY} seconds to avoid rate limits...")
                time.sleep(API_BATCH_DELAY)
            
            try:
                # Evaluate the image
                is_good_image, reason = evaluate_image(client, image_file)
                
                if is_good_image:
                    logger.info(f"KEEPING image {image_file.name}: {reason}")
                    stats["kept"] += 1
                    stats["by_style"][style_name]["kept"] += 1
                else:
                    logger.info(f"REMOVING image {image_file.name}: {reason}")
                    stats["removed"] += 1
                    stats["by_style"][style_name]["removed"] += 1
                    
                    # Also delete the corresponding metadata file if it exists
                    metadata_file = image_file.with_suffix(".txt")
                    
                    # Actually delete the files if not a dry run
                    if not dry_run:
                        try:
                            image_file.unlink()
                            logger.info(f"Deleted {image_file.name}")
                            
                            if metadata_file.exists():
                                metadata_file.unlink()
                                logger.info(f"Deleted metadata file {metadata_file.name}")
                        except Exception as e:
                            logger.error(f"Error deleting file {image_file.name}: {e}")
                            stats["errors"] += 1
                            stats["by_style"][style_name]["errors"] += 1
            
            except Exception as e:
                logger.error(f"Error processing {image_file.name}: {e}")
                stats["errors"] += 1
                stats["by_style"][style_name]["errors"] += 1
        
        logger.info(f"Completed style {style_name}: "
                   f"Kept {stats['by_style'][style_name]['kept']}, "
                   f"Removed {stats['by_style'][style_name]['removed']}, "
                   f"Errors {stats['by_style'][style_name]['errors']}")
    
    # Save results to a log file
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    results_file = results_dir / f"image_evaluation_results_{timestamp}.json"
    
    with open(results_file, "w") as f:
        json.dump(stats, f, indent=2)
    
    logger.info(f"Results saved to {results_file}")
    
    # Print summary
    logger.info("\n============= SUMMARY =============")
    logger.info(f"Total images processed: {stats['total_processed']}")
    logger.info(f"Images kept: {stats['kept']} ({stats['kept']/max(stats['total_processed'], 1):.1%})")
    logger.info(f"Images removed: {stats['removed']} ({stats['removed']/max(stats['total_processed'], 1):.1%})")
    logger.info(f"Errors: {stats['errors']}")
    logger.info("==================================\n")
    
    if dry_run:
        logger.info("This was a DRY RUN. No images were actually deleted.")
        logger.info("To perform actual deletion, run with --delete flag")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Evaluate and clean room style images using GPT-4o")
    parser.add_argument("--delete", action="store_true", help="Actually delete bad images (default is dry run)")
    parser.add_argument("--limit", type=int, help="Limit the number of images to process (for testing)")
    args = parser.parse_args()
    
    # Run with parameters
    process_directories(dry_run=not args.delete, limit=args.limit)

if __name__ == "__main__":
    main() 