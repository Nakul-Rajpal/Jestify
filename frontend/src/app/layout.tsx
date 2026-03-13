import type { Metadata } from "next";
import { Poppins } from "next/font/google";
import "./globals.css";

const poppins = Poppins({
  variable: "--font-poppins",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
});

export const metadata: Metadata = {
  title: "Jestify — The AI Analogy Engine",
  description:
    "Jestify transforms your boring syllabus into personalized explainer videos. AI analogies tailored to your interests—narrated by your favorite personas.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="scroll-smooth">
      <body
        className={`${poppins.variable} antialiased font-sans`}
      >
        {children}
      </body>
    </html>
  );
}
