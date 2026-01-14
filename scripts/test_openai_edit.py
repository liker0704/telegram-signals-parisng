#!/usr/bin/env python3
import os
import time
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI
from PIL import Image

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Create test files on disk
img = Image.new('RGBA', (1024, 1024), (255, 255, 255, 255))
img.save('/tmp/test_img.png', 'PNG')

mask = Image.new('RGBA', (1024, 1024), (0, 0, 0, 0))
mask.save('/tmp/test_mask.png', 'PNG')

print('Testing images.edit...')
start = time.time()

with open('/tmp/test_img.png', 'rb') as img_f, open('/tmp/test_mask.png', 'rb') as mask_f:
    response = client.images.edit(
        model='gpt-image-1',
        image=img_f,
        mask=mask_f,
        prompt='A white square',
        n=1,
        size='1024x1024'
    )

print(f'Success in {time.time()-start:.1f}s')
