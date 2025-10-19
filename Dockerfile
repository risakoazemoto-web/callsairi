FROM mcr.microsoft.com/azure-functions/python:4-python3.10

# ffmpeg を入れる（m4a対応）
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# 依存パッケージ
COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

# 関数コード
COPY . /home/site/wwwroot
