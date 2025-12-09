import asyncio
import argparse
import logging
from pathlib import Path

from app.hikvision_client import HikvisionClient


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("register_user_test")


async def register_user(ip: str, username: str, password: str, employee_no: str, name: str, department: str, photo_path: Path):
    if not photo_path.exists():
        raise FileNotFoundError(f"Photo not found: {photo_path}")

    photo_bytes = photo_path.read_bytes()
    client = HikvisionClient(ip, username, password)

    logger.info("Ensuring FDLib exists (normalFD, FDID=1)...")
    ensure = await client.ensure_fdlib_exists()
    if not ensure.get("success"):
        raise RuntimeError(f"Failed to ensure FDLib: {ensure.get('error')}")

    logger.info("Creating user without face (basic)...")
    user_res = await client.create_user_basic(employee_no, name, department or None)
    if not user_res.get("success"):
        raise RuntimeError(f"Failed to create user: {user_res.get('error')}")

    logger.info("Uploading face via FaceDataRecord...")
    face_res = await client.add_face_to_user_json(employee_no, photo_bytes, name)
    if not face_res.get("success"):
        raise RuntimeError(f"Failed to add face: {face_res.get('error')}")

    logger.info("✅ User and face saved on terminal.")
    return face_res


async def main():
    parser = argparse.ArgumentParser(description="Register user with face on Hikvision terminal (DS-K1T343EFWX).")
    parser.add_argument("--ip", required=True, help="Terminal IP")
    parser.add_argument("--user", required=True, help="Terminal username")
    parser.add_argument("--password", required=True, help="Terminal password")
    parser.add_argument("--employee", required=True, help="Employee No / ID")
    parser.add_argument("--name", required=True, help="Full name")
    parser.add_argument("--department", default="", help="Department (optional)")
    parser.add_argument("--photo", default="test_photo.jpg", help="Path to photo (JPEG)")
    args = parser.parse_args()

    photo_path = Path(args.photo)
    res = await register_user(args.ip, args.user, args.password, args.employee, args.name, args.department, photo_path)
    logger.info(f"Result: {res}")


if __name__ == "__main__":
    asyncio.run(main())

