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

def get_presigned_url(file_type: str) -> dict:
    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("AWS_SECRET_KEY"),
        region_name=os.getenv("AWS_REGION")
    )
    filename = f"{uuid4()}"
    presigned_url = s3.generate_presigned_url(
        ClientMethod='put_object',
        Params={
            'Bucket': os.getenv("AWS_S3_BUCKET"),
            'Key': filename + '.' + file_type,
        },
        ExpiresIn=3600
    )
    return {"url": presigned_url, "key": filename}