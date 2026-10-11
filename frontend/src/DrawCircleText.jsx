import React from "react";
import { motion } from "framer-motion";

export const DrawCircleText = () => {
  return (
    <div style={{
      display: 'grid', placeContent: 'center',
      background: '#f0fdf9', padding: '96px 24px',
      fontFamily: 'Montserrat, sans-serif'
    }}>
      <h1 style={{
        maxWidth: '38ch', textAlign: 'center',
        fontSize: 'clamp(28px, 4vw, 48px)', lineHeight: 1.45,
        fontWeight: 300, color: '#0f172a', letterSpacing: '-0.01em'
      }}>
        Turn your utility bills into a{" "}
        <span style={{ position: 'relative', display: 'inline-block', padding: '0 8px' }}>
          clear action plan
          <svg
            viewBox="0 0 420 80"
            fill="none"
            style={{ position: 'absolute', inset: 0, top: '-8px', bottom: '-48px', left: '-32px', right: '-32px', width: 'calc(100% + 64px)', height: 'auto' }}
          >
            <motion.path
              initial={{ pathLength: 0 }}
              whileInView={{ pathLength: 1 }}
              transition={{ duration: 1.8, ease: "easeInOut" }}
              d="M15 40 Q50 8, 120 10 Q200 12, 280 10 Q350 8, 405 40 Q410 50, 390 58 Q330 70, 260 68 Q160 70, 90 68 Q10 58, 15 40 Z"
              stroke="#0d9488"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <motion.path
              initial={{ pathLength: 0 }}
              whileInView={{ pathLength: 1 }}
              transition={{ duration: 2, ease: "easeInOut", delay: 0.2 }}
              d="M20 42 Q55 5, 125 7 Q205 9, 285 7 Q365 5, 400 42 Q405 52, 385 60 Q325 72, 255 70 Q155 72, 85 70 Q15 60, 20 42 Z"
              stroke="rgba(13,148,136,0.35)"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>{" "}
        with <strong style={{ fontWeight: 700, color: '#0d9488' }}>IN-TELLUS</strong>
      </h1>
    </div>
  );
};