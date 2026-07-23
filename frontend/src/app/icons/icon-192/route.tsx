import { ImageResponse } from "next/og";
import { BrandMark } from "@/app/brand-mark";

export async function GET() {
  return new ImageResponse(<BrandMark size={192} />, {
    width: 192,
    height: 192,
    headers: { "Cache-Control": "public, max-age=31536000, immutable" },
  });
}
