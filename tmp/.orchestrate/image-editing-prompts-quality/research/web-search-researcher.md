# Image Editing API Prompts: Best Practices Research Report

## Executive Summary

Исследование лучших практик для промптов OpenAI DALL-E/GPT-Image и Google Gemini выявило критические недостатки в текущем подходе и предоставило конкретные рекомендации по улучшению качества редактирования изображений с текстом.

### Ключевые находки:

1. **OpenAI**: Модели `gpt-image-1` и `gpt-image-1.5` заменили DALL-E 3 и поддерживают endpoint `images.edit()`
2. **Маски**: Полностью белая маска — неправильный подход; требуется прозрачная PNG с alpha-каналом
3. **Промпты**: Критически важно явно указывать, что должно остаться неизменным, а не только что изменить
4. **Текст**: Специальные техники для работы с текстом: кавычки, CAPS, побуквенное написание

---

## 1. OpenAI GPT-Image API: Best Practices

### 1.1 Выбор модели и API

**Текущее состояние моделей (2025):**
- `gpt-image-1.5` — state-of-the-art модель (рекомендуется)
- `gpt-image-1` — предыдущее поколение
- `gpt-image-1-mini` — быстрая версия
- `dall-e-2` — поддерживается, но устаревшая
- `dall-e-3` — deprecated, будет удалена

**Endpoint для редактирования:**
```python
client.images.edit(
    model="gpt-image-1",  # или gpt-image-1.5
    image=image_file,
    mask=mask_file,       # опционально
    prompt=prompt,
    size="1024x1024",
    quality="high"        # low/medium/high
)
```

**Источники:**
- [OpenAI Image Generation API Guide 2025](https://www.cursor-ide.com/blog/openai-image-generation-api-guide-2025)
- [Image generation | OpenAI API](https://platform.openai.com/docs/guides/image-generation)
- [GPT-Image-1 API Guide | DataCamp](https://www.datacamp.com/tutorial/gpt-image-1)

### 1.2 Правильное использование масок

**Критическая ошибка в текущей реализации:**
Используется полностью белая маска — это неправильно!

**Правильный подход:**

1. **Формат маски:** PNG с alpha-каналом
2. **Прозрачность:** Полностью прозрачные пиксели (alpha = 0) указывают области для редактирования
3. **Непрозрачность:** Непрозрачные области остаются неизменными

**Пример создания маски с alpha-каналом:**
```python
from PIL import Image
from io import BytesIO

# Загрузить черно-белую маску как grayscale
mask = Image.open(img_path_mask).convert("L")

# Конвертировать в RGBA
mask_rgba = mask.convert("RGBA")

# Использовать маску для заполнения alpha-канала
mask_rgba.putalpha(mask)

# Конвертировать в байты
buf = BytesIO()
mask_rgba.save(buf, format="PNG")
mask_bytes = buf.getvalue()
```

**Важные технические требования:**
- Маска должна иметь те же размеры, что и исходное изображение
- Для `gpt-image-1`: PNG/WebP/JPG < 50MB, до 16 изображений
- Для `dall-e-2`: только квадратные PNG < 4MB, 1 изображение
- Максимальная длина промпта: 32000 символов для GPT-Image, 1000 для DALL-E 2

**Источники:**
- [How To Create OpenAI DALL·E Mask Images | Medium](https://medium.com/@david.richards.tech/how-to-create-openai-dall-e-mask-images-ed8feb562eba)
- [Image generation | OpenAI API](https://platform.openai.com/docs/guides/image-generation)

### 1.3 Различия в поведении масок: DALL-E 2 vs GPT-Image

**Критическое различие:**
- **DALL-E 2**: Делает pixel-level замену только в замаскированных областях
- **GPT-Image-1**: Использует "soft mask" с пересозданием всего изображения

Это означает, что gpt-image-1 может изменить части изображения даже внутри маски, хотя старается этого избежать.

**Источник:**
- [Image editing with mask for gpt-image-1 - OpenAI Community](https://community.openai.com/t/image-editing-inpainting-with-a-mask-for-gpt-image-1-replaces-the-entire-image/1244275)

### 1.4 Структура промптов для редактирования

**Фундаментальный принцип:**
> Четко разделяйте, что должно измениться и что должно остаться неизменным, и повторяйте инварианты в каждой итерации, чтобы предотвратить drift.

**Шаблон промпта:**

```
[ОПИСАНИЕ ДЕЙСТВИЯ] + [ЧТО СОХРАНИТЬ] + [ОГРАНИЧЕНИЯ]
```

**Примеры:**

**❌ Плохо (текущий подход):**
```
Replace the following text on the image: [old] with [new]
```

**✅ Хорошо:**
```
Using the provided image, replace the text "[OLD TEXT]" with "[NEW TEXT]".
Preserve the exact original font style, size, color, and positioning.
Keep all other elements of the image completely unchanged: background,
layout, other text, graphics, and overall composition.
Do not add any watermarks, logos, or extra text.
```

**Шаблон для замены текста с сохранением стиля:**
```
Change only the text "[OLD]" to "[NEW]" while maintaining:
- The exact same font family and typeface
- The same font size and weight
- The same text color and effects
- The same position and alignment
- All other text and elements unchanged
Do not modify the background, layout, or any other part of the image.
```

**Источники:**
- [Gpt-image-1.5 Prompting Guide | OpenAI Cookbook](https://cookbook.openai.com/examples/multimodal/image-gen-1.5-prompting_guide)
- [GPT Image 1.5 Prompt Guide | fal.ai](https://fal.ai/learn/devs/gpt-image-1-5-prompt-guide)

### 1.5 Специальные техники для работы с текстом

**Проблема:** Модели часто некорректно генерируют текст (дубликаты букв, замены, искажения).

**Решения:**

1. **Используйте кавычки или CAPS для литерального текста:**
   ```
   Replace the text "SPECIAL OFFER" with "NEW DEAL"
   ```

2. **Указывайте типографические детали:**
   ```
   Change the headline to "SUMMER SALE" in bold sans-serif font,
   48pt size, red color (#FF0000), centered alignment
   ```

3. **Для сложных слов — побуквенное написание:**
   ```
   Replace with the brand name: C-O-C-A-C-O-L-A (Coca-Cola)
   ```

4. **Явное указание на отсутствие дополнительного текста:**
   ```
   No watermarks, no extra text, no logos/trademarks
   ```

**Источники:**
- [Gpt-image-1.5 Prompting Guide | OpenAI Cookbook](https://cookbook.openai.com/examples/multimodal/image-gen-1.5-prompting_guide)
- [Best prompt for precise TEXT on DALL-E 3 - OpenAI Community](https://community.openai.com/t/best-prompt-for-generating-precise-text-on-dall-e-3/428453)

### 1.6 Техники сохранения стиля

**Ключевые принципы:**

1. **Явно перечисляйте инварианты:**
   ```
   Preserve identity, geometry, layout, and all brand elements.
   Keep the same lighting, shadows, and color temperature.
   Maintain identical subject placement, scale, and pose.
   ```

2. **Используйте "change only X" формулировки:**
   ```
   Change only the text in the header. Keep everything else the same.
   ```

3. **Повторяйте ограничения в каждой итерации:**
   Если делаете несколько правок подряд, каждый раз повторяйте, что должно сохраниться.

4. **Для сохранения лица/персонажа:**
   ```
   Do not change her face, facial features, skin tone, body shape, pose,
   or identity in any way. Preserve her exact likeness, expression,
   hairstyle, and proportions.
   ```

**Источники:**
- [Gpt-image-1.5 Prompting Guide | OpenAI Cookbook](https://cookbook.openai.com/examples/multimodal/image-gen-1.5-prompting_guide)
- [Image editing API prompt guide - Black Forest Labs](https://docs.bfl.ml/guides/prompting_guide_kontext_i2i)

### 1.7 Параметры качества

**Quality:**
- `high` (default) — для продакшена, финальных результатов
- `medium` — для быстрой итерации в процессе разработки
- `low` — для черновых концептов, когда важна скорость

**Input Fidelity:**
При использовании референсных изображений параметр `input_fidelity` контролирует, насколько точно выход следует исходному материалу.

**Источник:**
- [GPT-Image-1 API Guide | DataCamp](https://www.datacamp.com/tutorial/gpt-image-1)

### 1.8 Итеративный подход

**Рекомендация:** Не пытайтесь все сделать в одном промпте.

**Стратегия:**
1. Сгенерировать базовое изображение
2. Уточнить с помощью follow-up промптов:
   ```
   Make the lighting warmer, keep the subject unchanged.
   ```

**Обработка ошибок:**
- Всегда обрабатывайте rate limit errors (HTTP 429)
- Реализуйте exponential backoff для повторных попыток
- Обрабатывайте invalid parameter responses (HTTP 400)

**Источники:**
- [GPT-Image-1 API Guide | DataCamp](https://www.datacamp.com/tutorial/gpt-image-1)
- [Mastering OpenAI's Image Generation API](https://www.cohorte.co/blog/mastering-openais-new-image-generation-api-a-developers-guide)

---

## 2. Google Gemini: Best Practices

### 2.1 Модели и возможности

**Актуальные модели (2025):**
- Gemini 2.5 Flash Image Generation
- Nano Banana Pro (кодовое название)

**Ключевые преимущества:**
- Сильная сторона в локальных правках
- Отличная консистентность персонажей
- Сохранение пропорций исходного изображения
- Conversational editing (итеративное улучшение)

**Источники:**
- [Tips for image generation in Gemini app | Google Blog](https://blog.google/products/gemini/image-generation-prompting-tips/)
- [How to prompt Gemini 2.5 Flash | Google Developers Blog](https://developers.googleblog.com/en/how-to-prompt-gemini-2-5-flash-image-generation-for-the-best-results/)

### 2.2 Структура промптов

**6 основных элементов:**

1. **Subject** — кто/что изображено (будьте конкретны)
2. **Composition** — кадрирование (wide shot, close-up, macro, etc.)
3. **Action** — что происходит в сцене
4. **Location** — место и окружение
5. **Style** — эстетика (photorealistic, watercolor, film noir)
6. **Editing Instructions** — инструкции по изменениям

**Пример структурированного промпта:**
```
Subject: A stoic robot barista with glowing blue optics
Composition: Extreme close-up, 85mm portrait lens
Action: Pouring steamed milk into a cappuccino
Location: Modern minimalist café with concrete walls
Style: Photorealistic with cinematic lighting
Editing: Change the coffee cup to a red ceramic mug
```

**Источники:**
- [Tips for image generation in Gemini app | Google Blog](https://blog.google/products/gemini/image-generation-prompting-tips/)
- [How to prompt Gemini 2.5 Flash | Google Developers Blog](https://developers.googleblog.com/en/how-to-prompt-gemini-2-5-flash-image-generation-for-the-best-results/)

### 2.3 Редактирование изображений

**Базовый подход:**
Просто предоставьте изображение и опишите изменение. Модель проанализирует оригинальный стиль, освещение и перспективу, чтобы правки выглядели естественно.

**Шаблон для редактирования:**
```
Using the provided image of [subject], please [add/remove/modify] [element].
Keep everything else in the image exactly the same, preserving the original
style, lighting, and composition.
```

**Пример целевого inpainting:**
```
Change only the [specific element] to [new element/description].
Keep everything else in the image exactly the same, preserving the original
style, lighting, and composition.
```

**Источник:**
- [How to prompt Gemini 2.5 Flash | Google Developers Blog](https://developers.googleblog.com/en/how-to-prompt-gemini-2-5-flash-image-generation-for-the-best-results/)

### 2.4 Сохранение пропорций и стиля

**Сохранение aspect ratio:**
Gemini 2.5 Flash обычно сохраняет пропорции входного изображения. Если не сохраняет, добавьте:
```
Do not change the input aspect ratio.
```

**Указание, что должно остаться:**
```
Keep my original facial features.
Maintain natural skin tones.
Preserve the exact camera angle, position, and framing.
```

**Источники:**
- [How to prompt Gemini 2.5 Flash | Google Developers Blog](https://developers.googleblog.com/en/how-to-prompt-gemini-2-5-flash-image-generation-for-the-best-results/)
- [TOP 10 Google Gemini Photo Editing Prompts | Skylum Blog](https://skylum.com/blog/gemini-ai-photo-editing-prompts)

### 2.5 Conversational редактирование

**Преимущество Gemini:** Поддержка итеративного улучшения через последовательные промпты.

**Пример диалога:**
1. Первый промпт: "Edit this image to add a beach background"
2. Follow-up: "That's great, but can you make the lighting warmer?"
3. Follow-up: "Perfect, now make the sky more dramatic with clouds"

**Важно:** В рамках одной сессии можно ссылаться на персонажей из предыдущих промптов для поддержания консистентности.

**Источник:**
- [How to prompt Gemini 2.5 Flash | Google Developers Blog](https://developers.googleblog.com/en/how-to-prompt-gemini-2-5-flash-image-generation-for-the-best-results/)

### 2.6 Использование фотографической терминологии

**Для контроля композиции используйте:**
- Wide-angle shot
- Macro shot
- Low-angle perspective
- 85mm portrait lens
- Dutch angle
- Bokeh effect
- Golden hour lighting
- High-key / low-key lighting

**Пример:**
```
Transform this image to a wide-angle shot with low-angle perspective,
preserving all subjects and elements but changing the camera view.
```

**Источник:**
- [How to prompt Gemini 2.5 Flash | Google Developers Blog](https://developers.googleblog.com/en/how-to-prompt-gemini-2-5-flash-image-generation-for-the-best-results/)

### 2.7 Лучшие практики для промптов

**Простота и прямота:**
Лучшие промпты — простые и прямые. Избегайте длинных объяснений, фокусируйтесь на одной цели за раз.

**Явный запрос изображения:**
Используйте фразы "create an image of" или "generate an image of", иначе модель может ответить текстом.

**Структура для редактирования:**
1. Определите субъект и что важнее всего
2. Выберите категорию редактирования: light, color, cleanup, texture, crop
3. Добавьте ограничения, чтобы модель знала, как далеко зайти
4. Укажите, что должно остаться нетронутым
5. Дайте 1-2 числовых направления для предсказуемой интенсивности

**Источники:**
- [Generate & edit images | Vertex AI Documentation](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/image-generation)
- [How to prompt Gemini 2.5 Flash | Google Developers Blog](https://developers.googleblog.com/en/how-to-prompt-gemini-2-5-flash-image-generation-for-the-best-results/)

### 2.8 Ограничения и особенности

**Текущие ограничения:**
- Иногда опечатки в тексте
- Непоследовательная стилизация (улучшается)
- Проблемы с aspect ratio (требует явного указания)
- Сложная типографика может требовать итераций
- Абсолютная консистентность персонажей требует уточнения

**Не используйте негативные промпты:**
Вместо "no cars" укажите, что вы хотите видеть: "peaceful park with walking paths and trees"

**Источники:**
- [Tips for image generation in Gemini app | Google Blog](https://blog.google/products/gemini/image-generation-prompting-tips/)
- [How to prompt Gemini 2.5 Flash | Google Developers Blog](https://developers.googleblog.com/en/how-to-prompt-gemini-2-5-flash-image-generation-for-the-best-results/)

---

## 3. Общие Best Practices для обоих API

### 3.1 Универсальные принципы

**1. Специфичность и детальность:**
Чем конкретнее промпт, тем лучше результат. Включайте детали о настройке, объектах, цветах, настроении.

**2. Явное указание инвариантов:**
```
State exclusions and invariants explicitly:
- "no watermark"
- "no extra text"
- "no logos/trademarks"
- "preserve identity/geometry/layout/brand elements"
```

**3. Формула "change only X" + "keep everything else":**
```
Change only [specific element] to [new state].
Keep everything else the same: [list invariants].
```

**4. Повторение сохраняемых элементов:**
При итерациях повторяйте список того, что должно остаться неизменным, чтобы предотвратить "drift".

**Источники:**
- [Gpt-image-1.5 Prompting Guide | OpenAI Cookbook](https://cookbook.openai.com/examples/multimodal/image-gen-1.5-prompting_guide)
- [Image editing prompt guide - Black Forest Labs](https://docs.bfl.ml/guides/prompting_guide_kontext_i2i)
- [AI Image Editing Prompt Guide | Gempix](https://gempix.ai/guides/ai-image-editing-prompt-guide)

### 3.2 Работа с текстом на изображениях

**Общие техники:**

1. **Кавычки для точного текста:**
   ```
   Replace "OLD TEXT" with "NEW TEXT"
   ```

2. **Указание стиля шрифта:**
   ```
   Use the same font style: [bold/italic/regular]
   Font size: [specific size or "same as original"]
   Color: [hex code or "same as original"]
   ```

3. **Позиционирование:**
   ```
   Keep the exact same position and alignment
   Centered / Left-aligned / Right-aligned at [coordinates]
   ```

4. **Для inpainting текста — минимальная маска:**
   Для сохранения стиля шрифта выделяйте только конкретные символы, а не весь текстовый блок.

**Источники:**
- [Midjourney V6: Correcting Typos with Inpainting | Medium](https://medium.com/design-bootcamp/midjourney-v6-a-simple-method-for-correcting-typos-with-inpainting-037b9b566e58)
- [Free AI Image Editing | Raphael AI](https://raphaelai.org/image-editing)

### 3.3 Шаблоны промптов для замены текста

**Базовый шаблон:**
```
Task: Replace text on the provided image
Original text: "[OLD_TEXT]"
New text: "[NEW_TEXT]"

Requirements:
- Preserve the exact font family, size, weight, and style
- Keep the same text color and any effects (shadow, outline, etc.)
- Maintain the exact position, alignment, and rotation
- Do not modify any other text or elements in the image
- Do not change the background, layout, or composition
- No watermarks, no extra text, no logos
```

**Расширенный шаблон с контекстом:**
```
Using the provided image showing [brief description],
replace only the text "[OLD_TEXT]" with "[NEW_TEXT]".

Preserve completely unchanged:
- Font: [family], [size], [weight], [style]
- Color: [hex code or description]
- Position: [location description]
- All other text and graphic elements
- Background and overall composition
- Image quality and resolution

Do not add:
- Watermarks or signatures
- Extra text or labels
- Logos or branding
- Any new visual elements
```

**Источники:**
- [Free AI Image Editing | Raphael AI](https://raphaelai.org/image-editing)
- [AI Image Editing Prompt Guide | Gempix](https://gempix.ai/guides/ai-image-editing-prompt-guide)

### 3.4 Предотвращение нежелательных изменений

**Техники:**

1. **Именование субъектов напрямую:**
   - ❌ "Change her dress to red"
   - ✅ "Change the woman's dress to red"

2. **Явное указание границ:**
   ```
   Change the background to a beach while keeping the person in the exact
   same position, scale, and pose. Add "maintain identical subject placement."
   ```

3. **Указание областей без изменений:**
   ```
   All areas outside the [specified region] remain completely unchanged,
   ensuring pixel-perfect preservation of unedited regions.
   ```

**Источник:**
- [Image editing API prompt guide - Gempix](https://gempix.ai/guides/ai-image-editing-prompt-guide)

### 3.5 Использование action verbs

**Выбор правильного глагола:**

- **Modifications:** Change, Make, Transform, Convert, Adjust, Modify
- **Additions:** Add, Include, Put, Insert, Place
- **Removals:** Remove, Delete, Take away, Erase, Eliminate
- **Replacements:** Replace, Swap, Substitute, Exchange

**Важно:**
- "Transform" — подразумевает полное изменение
- "Change the clothes" — более контролируемое изменение

**Источник:**
- [Free AI Image Editing | Raphael AI](https://raphaelai.org/image-editing)

---

## 4. Практические рекомендации для текущей реализации

### 4.1 Проблемы в текущем коде

**Идентифицированные проблемы:**

1. **Промпт слишком общий:**
   ```python
   # Текущий промпт (плохо):
   f"Replace the following text on the image: {old_text} with {new_text}.
   Keep the style and format similar to the original."
   ```

2. **Неправильная маска:**
   - Используется полностью белая маска
   - Отсутствует alpha-канал
   - Не учитывается различие между DALL-E 2 и GPT-Image

3. **Отсутствие контекста:**
   - Не описывается исходное изображение
   - Не указываются параметры шрифта
   - Не перечисляются элементы для сохранения

### 4.2 Рекомендуемые улучшения

**1. Улучшенный промпт для OpenAI:**

```python
def create_text_replacement_prompt(old_text: str, new_text: str,
                                   image_context: str = "") -> str:
    """
    Создает детальный промпт для замены текста с сохранением стиля.

    Args:
        old_text: Текст для замены
        new_text: Новый текст
        image_context: Краткое описание изображения (опционально)
    """
    prompt = f"""Replace the text "{old_text}" with "{new_text}" on this image.

PRESERVE COMPLETELY UNCHANGED:
- The exact font family, typeface, and weight
- The same font size and letter spacing
- The same text color, effects, and styling (bold/italic/etc.)
- The exact position, alignment, and rotation
- All other text elements in the image
- The background, layout, and overall composition
- Image quality and resolution

REQUIREMENTS:
- Match the original typography precisely
- Keep the new text in the exact same location
- Do not add watermarks, logos, or any extra text
- Do not modify any other part of the image
- Maintain the same visual style throughout
"""

    if image_context:
        prompt = f"Context: {image_context}\n\n" + prompt

    return prompt
```

**2. Улучшенный промпт для Gemini:**

```python
def create_gemini_text_replacement_prompt(old_text: str, new_text: str,
                                         style_hints: dict = None) -> str:
    """
    Создает промпт для Gemini с учетом его особенностей.

    Args:
        old_text: Текст для замены
        new_text: Новый текст
        style_hints: Опциональные подсказки о стиле
    """
    prompt = f"""Using the provided image, change only the text "{old_text}" to "{new_text}".

Keep exactly the same:
- Font style, size, and weight
- Text color and any effects
- Position and alignment
- All other text and graphic elements
- Background and composition
- Image aspect ratio and quality

Do not change the input aspect ratio.
Do not add any watermarks or extra elements.
"""

    if style_hints:
        if 'font_description' in style_hints:
            prompt += f"\nFont style: {style_hints['font_description']}"
        if 'color' in style_hints:
            prompt += f"\nText color: {style_hints['color']}"

    return prompt
```

**3. Правильная генерация маски:**

```python
from PIL import Image
from io import BytesIO
import numpy as np

def create_text_mask(image_path: str, text_bbox: tuple) -> BytesIO:
    """
    Создает маску с alpha-каналом для области текста.

    Args:
        image_path: Путь к исходному изображению
        text_bbox: Bounding box текста (x1, y1, x2, y2)

    Returns:
        BytesIO объект с PNG маской
    """
    # Загрузить изображение для получения размеров
    img = Image.open(image_path)
    width, height = img.size

    # Создать черную маску в grayscale
    mask = Image.new('L', (width, height), 0)

    # Белым отметить область текста (будет заменена)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(mask)
    draw.rectangle(text_bbox, fill=255)

    # Конвертировать в RGBA
    mask_rgba = mask.convert('RGBA')

    # Использовать grayscale значения как alpha-канал
    mask_rgba.putalpha(mask)

    # Сохранить в BytesIO
    buf = BytesIO()
    mask_rgba.save(buf, format='PNG')
    buf.seek(0)

    return buf
```

**4. Альтернативный подход — без маски:**

Для GPT-Image-1 можно попробовать вообще не использовать маску, так как модель делает "soft mask" с пересозданием изображения:

```python
# Без маски, но с очень детальным промптом
response = client.images.edit(
    model="gpt-image-1",
    image=open(image_path, "rb"),
    # mask=None  # не указываем маску
    prompt=detailed_prompt,
    size="1024x1024",
    quality="high"
)
```

### 4.3 Выбор между OpenAI и Gemini

**Используйте OpenAI когда:**
- Нужна максимальная точность текста
- Требуется pixel-perfect замена (DALL-E 2 с маской)
- Есть бюджет на high-quality запросы
- Работаете с брендированными материалами

**Используйте Gemini когда:**
- Нужна быстрая итерация
- Важна консистентность персонажей
- Требуется conversational editing
- Бюджет ограничен (Gemini более cost-effective)
- Работаете с художественными стилями

### 4.4 Параметры API для продакшена

**OpenAI:**
```python
{
    "model": "gpt-image-1",  # или gpt-image-1.5 для best quality
    "size": "1024x1024",     # или размер исходного изображения
    "quality": "high",       # для продакшена
    "n": 1,                  # генерировать 1 вариант
}
```

**Обработка ошибок:**
```python
import time
from openai import OpenAI, RateLimitError, APIError

def edit_image_with_retry(client, **kwargs):
    max_retries = 3
    base_delay = 1

    for attempt in range(max_retries):
        try:
            return client.images.edit(**kwargs)
        except RateLimitError:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
            else:
                raise
        except APIError as e:
            if e.status_code == 400:
                # Invalid parameters, не retry
                raise
            elif attempt < max_retries - 1:
                time.sleep(base_delay)
            else:
                raise
```

---

## 5. Примеры промптов из реальной практики

### 5.1 Замена текста на баннере

**Сценарий:** Рекламный баннер с заголовком и ценой.

**Промпт:**
```
Replace the text "SUMMER SALE" with "WINTER DEAL" in the header.
Replace the price "50% OFF" with "30% OFF" in the price tag.

Preserve:
- The exact bold sans-serif font family
- The same red color (#FF0000) for both texts
- The same font size (header: 48pt, price: 36pt)
- The centered alignment
- All graphic elements: background gradient, decorative shapes
- The overall layout and composition

Do not add watermarks or any extra text.
```

### 5.2 Обновление даты на сертификате

**Промпт:**
```
On this certificate image, change only the date "December 15, 2024"
to "January 10, 2025".

Keep completely unchanged:
- The serif font (appears to be Times New Roman or similar)
- The same italic style
- The same black text color
- The exact position below the recipient name
- All other text: title, recipient name, signatures
- The border, seal, and decorative elements
- The paper texture and background

Do not modify the certificate layout or add any elements.
```

### 5.3 Локализация UI элемента

**Промпт:**
```
Replace the button text "Submit" with "Отправить" (Russian).

Preserve exactly:
- The button's rounded rectangular shape and size
- The white text on blue background (#0066CC)
- The button's position in the lower right
- The same font weight (bold) and size (16pt)
- All other UI elements: input fields, labels, icons
- The overall interface layout and spacing

Ensure the Russian text is centered on the button.
Do not change the button size or any other interface elements.
```

---

## 6. Дополнительные ресурсы и инструменты

### 6.1 Инструменты для создания масок

1. **Segment Anything (Meta):**
   - Автоматическое выделение объектов
   - Интеграция с DALL-E через OpenAI Cookbook
   - [Пример](https://cookbook.openai.com/examples/dalle/how_to_create_dynamic_masks_with_dall-e_and_segment_anything)

2. **PIL/Pillow (Python):**
   - Программное создание масок
   - Полный контроль над alpha-каналом

3. **GIMP/Photoshop:**
   - Ручное создание точных масок
   - Экспорт с сохранением прозрачности

### 6.2 Полезные ссылки

**OpenAI Documentation:**
- [Image Generation Guide](https://platform.openai.com/docs/guides/image-generation)
- [Images API Reference](https://platform.openai.com/docs/api-reference/images)
- [GPT-Image-1.5 Prompting Guide](https://cookbook.openai.com/examples/multimodal/image-gen-1.5-prompting_guide)

**Google Gemini Documentation:**
- [Generate & edit images | Vertex AI](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/image-generation)
- [Gemini Image Generation Tips](https://blog.google/products/gemini/image-generation-prompting-tips/)
- [Gemini 2.5 Flash Prompting](https://developers.googleblog.com/en/how-to-prompt-gemini-2-5-flash-image-generation-for-the-best-results/)

**Community Resources:**
- [OpenAI Developer Community](https://community.openai.com/c/prompting/6)
- [r/StableDiffusion](https://reddit.com/r/StableDiffusion) — общие принципы применимы к любым моделям
- [Midjourney Inpainting Guide](https://medium.com/design-bootcamp/midjourney-v6-a-simple-method-for-correcting-typos-with-inpainting-037b9b566e58)

---

## 7. Выводы и рекомендации

### 7.1 Критические изменения для текущей реализации

1. **Немедленно исправить:**
   - Заменить белую маску на правильную PNG с alpha-каналом
   - Обновить промпты с явным указанием сохраняемых элементов
   - Добавить контекст изображения в промпт

2. **Важные улучшения:**
   - Реализовать детальные промпты с перечислением инвариантов
   - Использовать кавычки для литерального текста
   - Указывать параметры шрифта явно

3. **Опциональные оптимизации:**
   - Попробовать работу без маски для GPT-Image-1
   - Реализовать retry logic с exponential backoff
   - Добавить поддержку итеративного уточнения

### 7.2 Метрики качества

**Для оценки результатов отслеживайте:**

1. **Точность замены текста:**
   - Корректность текста (опечатки, дубликаты)
   - Сохранение шрифта и размера
   - Позиционирование

2. **Сохранение стиля:**
   - Неизменность фона
   - Сохранение других элементов
   - Качество изображения

3. **Производительность:**
   - Время генерации (обычно < 2 минуты)
   - Процент успешных запросов
   - Необходимость повторных попыток

### 7.3 Итоговые рекомендации

**Для замены текста на изображениях сигналов:**

1. **Используйте GPT-Image-1.5** как основной API (лучшее качество текста)
2. **Создавайте правильные маски** с alpha-каналом для областей текста
3. **Применяйте детальные промпты** с явным перечислением того, что сохранить
4. **Тестируйте итеративно:** сначала базовая замена, потом уточнение
5. **Fallback на Gemini** если OpenAI дает плохие результаты для конкретного стиля

**Шаблон финального промпта:**
```
Replace the text "{old_text}" with "{new_text}" on this trading signal image.

PRESERVE EXACTLY:
- Font: Same typeface, size, weight, and style as original
- Color: Same text color and any effects (shadow, glow, etc.)
- Position: Exact same location and alignment
- All other text: timestamps, prices, technical indicators
- All graphic elements: charts, lines, indicators, background
- Image quality and resolution
- Overall layout and composition

REQUIREMENTS:
- Use quotes around the exact text to replace
- Keep the new text perfectly aligned
- Do not add watermarks, logos, or extra text
- Do not modify charts, indicators, or any other elements
- Maintain professional trading signal appearance
```

---

## Metadata

```yaml
---
status: SUCCESS
sources_consulted: 28
sources_cited: 25
topics_covered:
  - OpenAI GPT-Image API usage and best practices
  - DALL-E 2 vs GPT-Image-1 differences
  - Proper mask creation with alpha channels
  - Prompt engineering for text replacement
  - Style and consistency preservation techniques
  - Google Gemini image editing capabilities
  - Conversational and iterative editing approaches
  - Typography and text rendering in AI models
  - Inpainting techniques and examples
  - Error handling and production parameters
search_queries_used: 10
confidence: high
---
```

## Sources

1. [OpenAI Image Generation API Guide 2025](https://www.cursor-ide.com/blog/openai-image-generation-api-guide-2025)
2. [Image generation | OpenAI API](https://platform.openai.com/docs/guides/image-generation)
3. [Images | OpenAI API Reference](https://platform.openai.com/docs/api-reference/images)
4. [How To Create OpenAI DALL·E Mask Images | Medium](https://medium.com/@david.richards.tech/how-to-create-openai-dall-e-mask-images-ed8feb562eba)
5. [How to create dynamic masks with DALL·E | OpenAI Cookbook](https://cookbook.openai.com/examples/dalle/how_to_create_dynamic_masks_with_dall-e_and_segment_anything)
6. [Tips for image generation in Gemini app | Google Blog](https://blog.google/products/gemini/image-generation-prompting-tips/)
7. [How to prompt Gemini 2.5 Flash | Google Developers Blog](https://developers.googleblog.com/en/how-to-prompt-gemini-2-5-flash-image-generation-for-the-best-results/)
8. [Gpt-image-1.5 Prompting Guide | OpenAI Cookbook](https://cookbook.openai.com/examples/multimodal/image-gen-1.5-prompting_guide)
9. [GPT-Image-1 API Guide | DataCamp](https://www.datacamp.com/tutorial/gpt-image-1)
10. [GPT Image 1.5 Prompt Guide | fal.ai](https://fal.ai/learn/devs/gpt-image-1-5-prompt-guide)
11. [Mastering OpenAI's Image Generation API](https://www.cohorte.co/blog/mastering-openais-new-image-generation-api-a-developers-guide)
12. [Image editing prompt guide - Black Forest Labs](https://docs.bfl.ml/guides/prompting_guide_kontext_i2i)
13. [Best prompt for precise TEXT on DALL-E 3 - OpenAI Community](https://community.openai.com/t/best-prompt-for-generating-precise-text-on-dall-e-3/428453)
14. [DALL-E Prompt Writing Guide](https://foundationinc.co/lab/dall-e-prompts/)
15. [Midjourney V6: Correcting Typos with Inpainting | Medium](https://medium.com/design-bootcamp/midjourney-v6-a-simple-method-for-correcting-typos-with-inpainting-037b9b566e58)
16. [Free AI Image Editing | Raphael AI](https://raphaelai.org/image-editing)
17. [AI Image Editing Prompt Guide | Gempix](https://gempix.ai/guides/ai-image-editing-prompt-guide)
18. [Image editing with mask for gpt-image-1 - OpenAI Community](https://community.openai.com/t/image-editing-inpainting-with-a-mask-for-gpt-image-1-replaces-the-entire-image/1244275)
19. [Generate & edit images | Vertex AI Documentation](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/image-generation)
20. [TOP 10 Google Gemini Photo Editing Prompts | Skylum Blog](https://skylum.com/blog/gemini-ai-photo-editing-prompts)
21. [Inpainting using Dall-E - AI Notebooks](https://scads.github.io/generative-ai-notebooks/40_image_generation_openai/51_inpainting_dall-e.html)
22. [How to Use OpenAI DALL-E for Inpainting](https://pantherax.com/how-to-use-openai-dall-e-for-image-inpainting/)
23. [OpenAI GPT-4o Image Generation Guide](https://img.ly/blog/openai-gpt-4o-image-generation-api-gpt-image-1-a-complete-guide-for-creative-workflows-for-2025/)
24. [Best Gemini Prompts for Image Generation 2025](https://www.media.io/image-effects/gemini-prompts.html)
25. [Nano Banana Pro prompting tips | Google Blog](https://blog.google/products/gemini/prompting-tips-nano-banana-pro/)
