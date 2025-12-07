"""
PaddleOCR Worker Module - runs in a separate process.

This module is designed to be imported by spawned processes.
It avoids issues with fork + asyncio by using clean process isolation.
"""

import sys


def run_ocr(image_path: str, result_queue):
    """
    Run PaddleOCR on an image in a clean subprocess.

    This function is called via multiprocessing with spawn method.
    It must be a module-level function to be picklable.

    Args:
        image_path: Path to image file
        result_queue: multiprocessing.Queue for returning results
    """
    try:
        # Import inside subprocess to ensure clean state
        from paddleocr import PaddleOCR

        # Initialize PaddleOCR
        ocr = PaddleOCR(lang='ru')

        # Run prediction
        result = ocr.predict(image_path)

        # Extract relevant data (OCRResult can't be pickled directly)
        if result and len(result) > 0:
            ocr_result = result[0]

            # Extract data from OCRResult dict-like object
            try:
                texts = ocr_result.get('rec_texts', []) if hasattr(ocr_result, 'get') else []
                polys = ocr_result.get('dt_polys', None)
                if polys is None:
                    polys = ocr_result.get('rec_polys', [])
                scores = ocr_result.get('rec_scores', [1.0] * len(texts))

                if polys is None:
                    polys = []
                if scores is None or len(scores) == 0:
                    scores = [1.0] * len(texts)

                # Convert numpy arrays to lists for pickling
                polys_list = []
                for poly in polys:
                    if hasattr(poly, 'tolist'):
                        polys_list.append(poly.tolist())
                    else:
                        polys_list.append(poly)

                result_queue.put(('success', {
                    'texts': texts,
                    'polys': polys_list,
                    'scores': list(scores)
                }))
            except Exception as e:
                result_queue.put(('error', f'Failed to parse OCR result: {e}'))
        else:
            result_queue.put(('success', {'texts': [], 'polys': [], 'scores': []}))

    except Exception as e:
        result_queue.put(('error', str(e)))


# Allow this module to be run directly for testing
if __name__ == '__main__':
    import multiprocessing as mp

    if len(sys.argv) < 2:
        print("Usage: python paddleocr_worker.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]
    result_queue = mp.Queue()

    print(f"Testing OCR on: {image_path}")
    run_ocr(image_path, result_queue)

    if not result_queue.empty():
        status, data = result_queue.get()
        print(f"Status: {status}")
        if status == 'success':
            print(f"Found {len(data.get('texts', []))} text elements")
            for text in data.get('texts', [])[:5]:
                print(f"  - {text}")
        else:
            print(f"Error: {data}")
