from PIL import Image, ImageDraw, ImageFont
import os

def create_logo():
    # Create a new image with a white background
    img_size = (192, 192)
    img = Image.new('RGBA', img_size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw a circle background
    circle_margin = 10
    circle_bbox = [circle_margin, circle_margin, 
                  img_size[0] - circle_margin, 
                  img_size[1] - circle_margin]
    draw.ellipse(circle_bbox, fill='#F97316')  # BlazeCore Orange
    
    # Add text
    text = "B"  # B for BlazeCore
    try:
        # Try to use Arial, fall back to default if not available
        font = ImageFont.truetype("arial.ttf", 100)
    except:
        font = ImageFont.load_default()
    
    # Get text size
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    # Calculate center position
    x = (img_size[0] - text_width) // 2
    y = (img_size[1] - text_height) // 2
    
    # Draw text in white
    draw.text((x, y), text, fill='white', font=font)
    
    # Save the image
    if not os.path.exists('static'):
        os.makedirs('static')
    img.save('static/logo.png', 'PNG')

if __name__ == "__main__":
    create_logo()