import { ImageResponse } from "next/og";
import { BrandMark } from "@/app/brand-mark";

export async function GET() {
  return new ImageResponse(<BrandMark size={512} />, {
    width: 512,
    height: 512,
    headers: { "Cache-Control": "public, max-age=31536000, immutable" },
  });
}
