import boto3
import aiohttp
import asyncio
from io import BytesIO
import os
import logging

logger = logging.getLogger(__name__)

class R2Uploader:
    def __init__(self, bucket_name, region_name="auto"):
        cf_r2_access_key = os.environ.get("CF_R2_ACCESS_KEY_ID")
        cf_r2_secret_key = os.environ.get("CF_R2_SECRET_ACCESS_KEY")
        cf_r2_endpoint = os.environ.get("CF_R2_ENDPOINT_URL")
        self.bucket_name = bucket_name
        self.R2 = boto3.client(
            "s3",
            endpoint_url=cf_r2_endpoint.rstrip("/").removesuffix("/" + bucket_name) if cf_r2_endpoint else cf_r2_endpoint,
            aws_access_key_id=cf_r2_access_key,
            aws_secret_access_key=cf_r2_secret_key,
            region_name='auto'
        )

    async def upload_fileobj(self, file_obj, R2_path, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"):
        try:
            logger.info(f"Uploading file to R2: {R2_path}")
            self.R2.upload_fileobj(file_obj, self.bucket_name, R2_path, ExtraArgs={"ContentType": content_type})
            R2_url = f"r2://{self.bucket_name}/{R2_path}"
            logger.info(f"[OK] File uploaded successfully: {R2_url}")
            return R2_url
        except Exception as e:
            logger.error(f"Failed to upload file to R2 {R2_path}: {e}", exc_info=True)
            raise

    async def upload_image(self, url, R2_path, retries=3):
        timeout = aiohttp.ClientTimeout(total=30)
        for attempt in range(1, retries + 1):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            content = await resp.read()
                            file_obj = BytesIO(content)
                            logger.debug(f"Uploading image to R2: {R2_path}")
                            self.R2.upload_fileobj(file_obj, self.bucket_name, R2_path, ExtraArgs={"ContentType": "image/jpeg"})
                            R2_url = f"r2://{self.bucket_name}/{R2_path}"
                            logger.debug(f"Image uploaded: {R2_url}")
                            return R2_url
                        else:
                            logger.warning(f"Failed to download {url} status={resp.status}")
                            return None
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                if attempt < retries:
                    wait = 2 ** attempt
                    logger.warning(f"Attempt {attempt}/{retries} failed for {url}: {e}. Retrying in {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"All {retries} attempts failed for {url} -> {R2_path}: {e}")
                    return None
            except Exception as e:
                logger.error(f"Error uploading image from {url} to {R2_path}: {e}", exc_info=True)
                return None
