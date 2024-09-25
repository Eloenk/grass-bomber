FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

LABEL maintainer="Eloenk"
LABEL description="Async grass-mining"

# Specify the Working-Dir of the conte
WORKDIR /grass-bomber

#
COPY . /grass-bomber

#
RUN pip install --no-cache-dir -r requirements.txt

# Install the required dependencies found in the requirements.txt file
EXPOSE 80

# RUn
CMD ["python", "grass.py"]
