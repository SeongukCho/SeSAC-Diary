import boto3, os
from dotenv import load_dotenv
from uuid import uuid4

load_dotenv()

s3 = boto3.client(
    "s3",
    region_name=os.getenv("AWS_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("AWS_SECRET_KEY")
)

BUCKET_NAME = os.getenv("AWS_S3_BUCKET")

def upload_file_to_s3(file, filename=None) -> str:
    ext = file.filename.split('.')[-1]
    filename = filename or f"{uuid4()}.{ext}"

    s3.upload_fileobj(
        file.file,
        BUCKET_NAME,
        filename,
        ExtraArgs={"ACL": "public-read", "ContentType": file.content_type}
    )

    return f"https://{BUCKET_NAME}.s3.{os.getenv('AWS_REGION')}.amazonaws.com/{filename}"
