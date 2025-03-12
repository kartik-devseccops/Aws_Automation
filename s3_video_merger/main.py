import boto3
import os
import subprocess
from datetime import datetime, timezone

# AWS S3 Configuration
BUCKET_NAME = "my-test-bucket-kartik"  # Replace with your bucket name
DOWNLOAD_PATH = "videos"  # Local folder for video downloads
MERGED_VIDEO = "merged_today.mp4"

# Initialize S3 Client
s3 = boto3.client("s3")

# Ensure the download directory exists
if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

def list_todays_videos():
    """Fetch only today's video files from S3 (assuming .mp4 format)"""
    today = datetime.now(timezone.utc).date()
    response = s3.list_objects_v2(Bucket=BUCKET_NAME)

    videos = []
    for obj in response.get("Contents", []):
        file_date = obj["LastModified"].date()  # Extract date from S3 object metadata
        if file_date == today and obj["Key"].endswith(".mp4"):
            videos.append(obj["Key"])
    
    return videos

def download_videos(video_files):
    """Download videos from S3"""
    local_files = []
    for video in video_files:
        local_path = os.path.join(DOWNLOAD_PATH, os.path.basename(video))
        s3.download_file(BUCKET_NAME, video, local_path)
        local_files.append(local_path)
        print(f"Downloaded: {video}")
    return local_files

def merge_with_ffmpeg(video_files, output_file):
    """Merge multiple videos into one using FFmpeg"""
    txt_file = os.path.join(DOWNLOAD_PATH, "videos_list.txt")

    # Create a text file with video file names for FFmpeg
    with open(txt_file, "w") as f:
        for video in video_files:
            f.write(f"file '{video}'\n")

    # FFmpeg command to merge videos
    cmd = f"ffmpeg -f concat -safe 0 -i {txt_file} -c copy {output_file}"
    subprocess.run(cmd, shell=True, check=True)
    print(f"Merged video saved as {output_file}")

def upload_to_s3(file_path):
    """Upload the final merged video to S3"""
    s3.upload_file(file_path, BUCKET_NAME, os.path.basename(file_path))
    print(f"Uploaded {file_path} to S3")

def cleanup(files):
    """Delete local files after merging"""
    for file in files:
        os.remove(file)
    print("Cleaned up local files")

if __name__ == "__main__":
    video_files = list_todays_videos()

    if not video_files:
        print("No videos found for today in the S3 bucket.")
        exit(1)

    downloaded_videos = download_videos(video_files)
    merge_with_ffmpeg(downloaded_videos, MERGED_VIDEO)
    upload_to_s3(MERGED_VIDEO)
    cleanup(downloaded_videos + [MERGED_VIDEO])
