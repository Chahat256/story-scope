import type { Metadata } from "next";
import "./globals.css";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "StoryScope — Literary Analysis for Novels",
  description:
    "Upload a novel and get deep, evidence-grounded literary analysis: characters, relationships, themes, and tropes.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-parchment">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
