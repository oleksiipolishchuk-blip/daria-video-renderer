FROM python:3.11-slim

# System deps: ffmpeg + font tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-liberation \
    wget \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Montserrat fonts (Regular + Bold)
RUN mkdir -p /usr/share/fonts/truetype/montserrat \
    && wget -q "https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-Regular.ttf" \
         -O /usr/share/fonts/truetype/montserrat/Montserrat-Regular.ttf \
    && wget -q "https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-Bold.ttf" \
         -O /usr/share/fonts/truetype/montserrat/Montserrat-Bold.ttf \
    && wget -q "https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-SemiBold.ttf" \
         -O /usr/share/fonts/truetype/montserrat/Montserrat-SemiBold.ttf \
    && fc-cache -f -v

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
