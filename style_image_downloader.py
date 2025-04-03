import os
import json
import time
import requests
import random
import logging
from io import BytesIO
from pathlib import Path
from PIL import Image
from openai import OpenAI
from dotenv import load_dotenv

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
STYLES_FILE = BASE_DIR / "styles.json"
IMAGES_PER_STYLE = 70
MIN_IMAGE_SIZE = 400  # Minimum width/height in pixels
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class StyleDownloader:
    """Manages downloading and organizing interior design style images"""
    
    def __init__(self):
        # Initialize session for requests
        self.session = requests.Session()
        # Set up Pexels API headers if key is available
        if PEXELS_API_KEY:
            self.session.headers.update({
                "Authorization": PEXELS_API_KEY
            })
    
    def generate_interior_design_styles(self):
        """Generate interior design styles using GPT-4o"""
        logger.info("Generating interior design styles using GPT-4o...")
        
        # Check if API key exists
        api_key = OPENAI_API_KEY
        if not api_key:
            logger.error("OpenAI API key not found in environment variables")
            raise ValueError("OpenAI API key is required to generate styles")
            
        logger.info("Making request to OpenAI API (this may take up to 60 seconds)...")
        
        try:
            # Create a client with timeout
            client = OpenAI(
                api_key=api_key,
                timeout=60.0  # 60 second timeout
            )
            
            # Make the API call with a timeout
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert interior designer with extensive knowledge of global design styles."
                    },
                    {
                        "role": "user",
                        "content": """Generate 15 distinct interior design styles for home decor.
                        For each style, provide:
                        1. A concise, search-friendly name (e.g., 'Scandinavian Minimalism', 'Industrial Loft')
                        2. A brief description (1-2 sentences)
                        3. 5 search keywords perfect for finding images of this style on Pinterest
                        
                        Your response must be a valid JSON object with the following structure:
                        {
                          "styles": [
                            {
                              "name": "Style Name 1",
                              "description": "Style description 1",
                              "search_keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
                            },
                            {
                              "name": "Style Name 2",
                              "description": "Style description 2",
                              "search_keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
                            },
                            ... and so on for all 15 styles
                          ]
                        }
                        
                        Include diverse styles from different regions, time periods, and design philosophies."""
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=2000
            )
            
            logger.info("Successfully received response from OpenAI API")
            
            # Parse the JSON response
            try:
                content = response.choices[0].message.content
                logger.info(f"API returned content of length: {len(content)} characters")
                logger.debug(f"Response content preview: {content[:200]}...")
                
                styles_json = json.loads(content)
                
                # Check the structure of the parsed JSON
                if isinstance(styles_json, dict) and "styles" in styles_json:
                    # If the API returned a valid JSON object with a styles key
                    logger.info("API returned a valid JSON object with a styles key")
                    styles = styles_json["styles"]
                else:
                    # If the API returned an unexpected structure
                    logger.error("API returned an unexpected structure")
                    logger.debug(f"Full API response: {content}")
                    raise ValueError("Unexpected response format from OpenAI API")
                
                if not styles:
                    logger.warning("No styles found in the API response")
                    # Print the actual API response for debugging
                    logger.debug(f"Full API response: {content}")
                    raise ValueError("No styles returned from OpenAI API")
                    
                logger.info(f"Successfully parsed {len(styles)} styles from response")
                return styles
                
            except json.JSONDecodeError as json_err:
                logger.error(f"Failed to parse JSON response: {json_err}")
                logger.error(f"Response content: {response.choices[0].message.content[:200]}...")
                raise
                
        except Exception as e:
            logger.error(f"OpenAI API request failed: {e}")
            raise
    
    def setup_directory_structure(self, styles):
        """Create directories for each style and save descriptions"""
        logger.info("Setting up directory structure...")
        
        if not BASE_DIR.exists():
            BASE_DIR.mkdir(parents=True)
            
        for style in styles:
            style_name = style["name"]
            style_dir = BASE_DIR / style_name.replace(" ", "_").lower()
            
            if not style_dir.exists():
                style_dir.mkdir(parents=True)
                logger.debug(f"Created directory for {style_name}")
            
            # Create description.txt with style info
            description_file = style_dir / "description.txt"
            try:
                with open(description_file, "w") as f:
                    f.write(f"Style: {style_name}\n\n")
                    f.write(f"Description: {style.get('description', 'No description provided')}\n\n")
                    if 'search_keywords' in style:
                        f.write("Keywords:\n")
                        for keyword in style['search_keywords']:
                            f.write(f"- {keyword}\n")
                logger.debug(f"Saved description for {style_name}")
            except Exception as e:
                logger.error(f"Error saving description for {style_name}: {e}")
    
    def check_existing_styles_and_images(self):
        """
        Check if styles.json exists and if style directories have images
        
        Returns:
            tuple: (existing_styles, styles_with_images, styles_without_images)
        """
        logger.info("Checking for existing styles and images...")
        
        if not BASE_DIR.exists() or not STYLES_FILE.exists():
            logger.info("No existing styles found")
            return [], [], []
        
        # Load existing styles
        try:
            with open(STYLES_FILE, "r") as f:
                data = json.load(f)
                existing_styles = data.get("styles", [])
                logger.info(f"Loaded {len(existing_styles)} existing styles from file")
        except Exception as e:
            logger.error(f"Error loading existing styles: {e}")
            return [], [], []
        
        styles_with_images = []
        styles_without_images = []
        
        # Check each style directory for images
        for style in existing_styles:
            style_name = style["name"]
            style_dir = BASE_DIR / style_name.replace(" ", "_").lower()
            
            if not style_dir.exists():
                styles_without_images.append(style)
                continue
            
            # Count images in directory
            image_files = list(style_dir.glob("*.jpg")) + list(style_dir.glob("*.jpeg")) + list(style_dir.glob("*.png"))
            
            # Add image_paths to the style object
            style["image_paths"] = [str(path) for path in image_files]
            
            # Check if description.txt exists, create if not
            description_file = style_dir / "description.txt"
            if not description_file.exists():
                try:
                    with open(description_file, "w") as f:
                        f.write(f"Style: {style_name}\n\n")
                        f.write(f"Description: {style.get('description', 'No description provided')}\n\n")
                        if 'search_keywords' in style:
                            f.write("Keywords:\n")
                            for keyword in style['search_keywords']:
                                f.write(f"- {keyword}\n")
                    logger.info(f"Created missing description file for {style_name}")
                except Exception as e:
                    logger.error(f"Error creating description file for {style_name}: {e}")
            
            if image_files:
                styles_with_images.append(style)
            else:
                styles_without_images.append(style)
        
        return existing_styles, styles_with_images, styles_without_images
    
    def download_pexels_images(self, style, max_images=IMAGES_PER_STYLE):
        """Download images from Pexels API for a specific style"""
        style_name = style["name"]
        search_keywords = style.get("search_keywords", [])
        if not search_keywords:
            logger.warning(f"No search keywords for style: {style_name}")
            return 0
            
        style_dir = BASE_DIR / style_name.replace(" ", "_").lower()
        
        # Use all search keywords to get diverse images
        images_per_keyword = max_images // len(search_keywords)
        
        total_downloaded = 0
        
        # Check if we have a valid Pexels API key (not placeholder)
        if not PEXELS_API_KEY or PEXELS_API_KEY == "your_pexels_api_key_here":
            logger.error("No valid Pexels API key found. Please add a valid API key to your .env file.")
            raise ValueError("Pexels API key is required to download images")
        
        # Validate API key with a test request
        test_url = "https://api.pexels.com/v1/search?query=test&per_page=1"
        try:
            test_response = self.session.get(test_url)
            if test_response.status_code != 200:
                logger.error(f"Pexels API key validation failed with status code {test_response.status_code}")
                logger.error(f"Response: {test_response.text}")
                raise ValueError("Invalid Pexels API key. Please check your .env file.")
            else:
                logger.info("✅ Pexels API key validated successfully!")
        except Exception as e:
            logger.error(f"Error validating Pexels API key: {e}")
            raise
        
        for keyword in search_keywords:
            # Try multiple search queries for better results
            search_queries = [
                f"{keyword} {style_name} interior",
                f"{style_name} {keyword} room",
                f"{keyword} interior design {style_name}"
            ]
            
            for search_query in search_queries:
                if total_downloaded >= images_per_keyword:
                    break
                    
                encoded_query = search_query.replace(" ", "%20")
                
                logger.info(f"Searching Pexels for '{search_query}'")
                
                # Make API request to Pexels
                pexels_url = f"https://api.pexels.com/v1/search?query={encoded_query}&per_page=30&orientation=landscape"
                try:
                    response = self.session.get(pexels_url)
                    
                    if response.status_code != 200:
                        logger.error(f"Pexels API error: {response.status_code} - {response.text}")
                        continue
                    
                    data = response.json()
                    photos = data.get("photos", [])
                    
                    # Show more details about the API response
                    total_results = data.get("total_results", 0)
                    logger.info(f"Pexels found {total_results} total results, returned {len(photos)} photos")
                    
                    if not photos:
                        logger.warning(f"No photos found for '{search_query}'")
                        continue
                    
                    # Shuffle to get a good mix
                    random.shuffle(photos)
                    
                    # Limit to remaining images per keyword
                    remaining = images_per_keyword - total_downloaded
                    photos = photos[:remaining]
                    
                    # Download images
                    for i, photo in enumerate(photos):
                        if total_downloaded >= max_images:
                            break
                        
                        try:
                            # Get the large size image URL
                            image_url = photo["src"]["large"]
                            photographer = photo.get("photographer", "Unknown")
                            
                            logger.info(f"Downloading from Pexels: {image_url} (by {photographer})")
                            img_response = self.session.get(image_url, stream=True)
                            
                            if img_response.status_code == 200:
                                # Process and save the image
                                img = Image.open(BytesIO(img_response.content))
                                
                                # Get image dimensions
                                width, height = img.size
                                logger.debug(f"Image dimensions: {width}x{height}")
                                
                                # Only save if it's large enough
                                if width >= MIN_IMAGE_SIZE and height >= MIN_IMAGE_SIZE:
                                    # Save image info in filename for attribution
                                    photo_id = photo.get("id", "unknown")
                                    img_path = style_dir / f"{keyword.replace(' ', '_')}_{photo_id}.jpg"
                                    img.save(img_path)
                                    total_downloaded += 1
                                    
                                    # Create a metadata file with attribution information
                                    meta_path = style_dir / f"{keyword.replace(' ', '_')}_{photo_id}.txt"
                                    with open(meta_path, "w") as f:
                                        f.write(f"Photo by: {photographer}\n")
                                        f.write(f"Source: Pexels (ID: {photo_id})\n")
                                        f.write(f"URL: {photo.get('url', 'Unknown')}\n")
                                        f.write(f"Size: {width}x{height}\n")
                                    
                                    logger.info(f"Downloaded Pexels image #{total_downloaded} for '{keyword}'")
                                else:
                                    logger.debug(f"Image too small: {width}x{height}")
                        except Exception as e:
                            logger.error(f"Error downloading image from Pexels: {e}")
                    
                    # If we got some images, move to the next keyword
                    if total_downloaded > 0:
                        break
                            
                except Exception as e:
                    logger.error(f"Error searching Pexels: {e}")
                    
        if total_downloaded == 0:
            logger.warning(f"Couldn't download any images from Pexels for {style_name}.")
            
        return total_downloaded

    def run(self):
        """Main process to generate styles and download images"""
        try:
            # Check for existing styles and images
            existing_styles, styles_with_images, styles_without_images = self.check_existing_styles_and_images()
            
            # If we have styles with images, report them
            if styles_with_images:
                logger.info(f"Found {len(styles_with_images)} styles with images:")
                for style in styles_with_images:
                    logger.info(f"  - {style['name']} ({len(style['image_paths'])} images)")
            
            # If we have styles without images, prepare to download images
            if styles_without_images:
                logger.info(f"\nFound {len(styles_without_images)} styles without images:")
                for style in styles_without_images:
                    logger.info(f"  - {style['name']}")
                
                styles_to_download = styles_without_images
                logger.info("\nWill download images for the above styles.")
            else:
                styles_to_download = []
            
            # If no existing styles or styles without images, generate new styles
            if not existing_styles or (not styles_with_images and not styles_without_images):
                logger.info("\nNo existing styles found or generating fresh styles.")
                new_styles = self.generate_interior_design_styles()
                
                if not new_styles:
                    logger.error("No styles were generated. Please check your OpenAI API key.")
                    return
                
                logger.info(f"Generated {len(new_styles)} interior design styles.")
                styles_to_download = new_styles
                
                # Setup directory structure for new styles
                self.setup_directory_structure(styles_to_download)
                
                # Save styles to JSON file
                with open(STYLES_FILE, "w") as f:
                    json.dump({"styles": styles_to_download}, f, indent=4)
                    logger.info(f"Saved styles to {STYLES_FILE}")
            
            # If no styles to download, exit
            if not styles_to_download:
                logger.info("\nAll styles already have images. Nothing to download.")
                return
            
            # Download images for styles that need them
            total_images = 0
            
            for i, style in enumerate(styles_to_download):
                logger.info(f"\nProcessing style {i+1}/{len(styles_to_download)}: {style['name']}")
                logger.info(f"Description: {style.get('description', 'No description')}")
                logger.info(f"Keywords: {', '.join(style.get('search_keywords', []))}")
                
                # Try to download images using Pexels API
                images_downloaded = self.download_pexels_images(style)
                total_images += images_downloaded
                
                logger.info(f"Completed downloading {images_downloaded} images for {style['name']}")
                
                # Small delay between styles
                time.sleep(1)
            
            logger.info(f"\nDownload complete! Total images: {total_images}")
            
        except Exception as e:
            logger.error(f"Error in main process: {e}")

def main():
    """Entry point for the script"""
    # Check for API keys and provide instructions
    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your_openai_api_key_here":
        logger.error("""
        ❌ Missing or invalid OpenAI API key. 
        Please add a valid API key to your .env file with: OPENAI_API_KEY=your_actual_key
        Get a key from https://platform.openai.com/api-keys
        
        Exiting...
        """)
        return
    
    if not PEXELS_API_KEY or PEXELS_API_KEY == "your_pexels_api_key_here":
        logger.error("""
        ❌ Missing or invalid Pexels API key.
        Please add a valid API key to your .env file with: PEXELS_API_KEY=your_actual_key
        Get a free API key from https://www.pexels.com/api/
        
        Exiting...
        """)
        return
    
    downloader = StyleDownloader()
    downloader.run()

if __name__ == "__main__":
    main() 