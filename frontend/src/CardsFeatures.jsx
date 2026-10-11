import React from "react";
import { motion } from "framer-motion";

/* The reveal panel is always visible — it just lifts slightly on hover */
const BounceCard = ({ children, style }) => (
  <motion.div
    whileHover={{ scale: 0.97, rotate: '-0.5deg' }}
    transition={{ type: 'spring', stiffness: 280, damping: 22 }}
    style={{
      position: 'relative',
      minHeight: 300,
      cursor: 'pointer',
      overflow: 'hidden',
      borderRadius: 16,
      padding: '32px 28px',
      display: 'flex',
      flexDirection: 'column',
      ...style,
    }}
  >
    {children}
  </motion.div>
);

const CardTitle = ({ children, dark }) => (
  <h3 style={{
    fontSize: 26, fontWeight: 700,
    color: dark ? '#0f172a' : '#f9fafb',
    fontFamily: 'Montserrat, sans-serif',
    marginBottom: 12,
  }}>
    {children}
  </h3>
);

const CardDesc = ({ children, dark }) => (
  <p style={{
    fontSize: 13,
    color: dark ? 'rgba(15,23,42,0.6)' : 'rgba(249,250,251,0.65)',
    lineHeight: 1.7,
    fontFamily: 'Montserrat, sans-serif',
  }}>
    {children}
  </p>
);

/* Decorative mini-content shown at bottom of each card */
function ExtractPreview() {
  return (
    <div style={{
      marginTop: 'auto', paddingTop: 24,
      borderTop: '1px solid rgba(15,23,42,0.1)',
    }}>
      {['resource_type: electricity', 'consumption: 1,840 kWh', 'billing_period: 2024-11'].map((line, i) => (
        <div key={i} style={{
          fontFamily: 'ui-monospace, monospace',
          fontSize: 11, color: 'rgba(15,23,42,0.5)',
          marginBottom: 4,
        }}>{line}</div>
      ))}
    </div>
  );
}

function AnalysePreview() {
  const bars = [
    { label: 'Fuel (Scope 1)', pct: 45, color: '#0d9488' },
    { label: 'Electricity (Scope 2)', pct: 72, color: 'rgba(13,148,136,0.45)' },
    { label: 'Water', pct: 20, color: 'rgba(13,148,136,0.2)' },
  ];
  return (
    <div style={{ marginTop: 'auto', paddingTop: 20 }}>
      {bars.map(b => (
        <div key={b.label} style={{ display: 'grid', gridTemplateColumns: '120px 1fr 48px', alignItems: 'center', gap: 10, marginBottom: 10 }}>
          <span style={{ fontSize: 11, color: 'rgba(249,250,251,0.55)', fontFamily: 'Montserrat, sans-serif' }}>{b.label}</span>
          <div style={{ height: 6, background: 'rgba(249,250,251,0.1)', borderRadius: 999, overflow: 'hidden' }}>
            <div style={{ width: `${b.pct}%`, height: '100%', background: b.color, borderRadius: 999 }} />
          </div>
          <span style={{ fontSize: 11, color: 'rgba(249,250,251,0.4)', textAlign: 'right', fontFamily: 'Montserrat, sans-serif' }}>{b.pct}%</span>
        </div>
      ))}
    </div>
  );
}

function RecommendPreview() {
  const items = [
    '↓ Switch to off-peak tariff — save ~LKR 12,400/mo',
    '☀ 18 kWp solar system — payback 4.2 years',
    '⚡ LED retrofit Kandy branch — 31% reduction',
  ];
  return (
    <div style={{ marginTop: 'auto', paddingTop: 20 }}>
      {items.map((item, i) => (
        <div key={i} style={{
          padding: '8px 12px', marginBottom: 8,
          background: 'rgba(249,250,251,0.06)',
          borderLeft: '2px solid rgba(249,250,251,0.3)',
          fontSize: 12, color: 'rgba(249,250,251,0.8)',
          lineHeight: 1.5, fontFamily: 'Montserrat, sans-serif',
        }}>
          {item}
        </div>
      ))}
    </div>
  );
}

function ReportPreview() {
  return (
    <div style={{ marginTop: 'auto', paddingTop: 24, borderTop: '1px solid rgba(13,148,136,0.15)' }}>
      {['✓ Scope-tagged emissions', '✓ Audit fingerprint', '✓ PDF download ready'].map((item, i) => (
        <div key={i} style={{
          fontSize: 12, color: '#0d9488',
          fontFamily: 'Montserrat, sans-serif',
          fontWeight: 600, marginBottom: 6,
        }}>{item}</div>
      ))}
    </div>
  );
}

export const CardsFeatures = () => {
  return (
    <section style={{ background: '#f9fafb', padding: '80px 48px', fontFamily: 'Montserrat, sans-serif' }}>
      <div style={{ maxWidth: 1100, margin: '0 auto' }}>

        {/* Header */}
        <div style={{
          display: 'flex', justifyContent: 'space-between',
          alignItems: 'flex-end', marginBottom: 48,
          flexWrap: 'wrap', gap: 20,
        }}>
          <div>
            <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.14em', color: '#0d9488', marginBottom: 12 }}>WHAT WE DO</p>
            <h2 style={{
              fontSize: 'clamp(26px, 3.5vw, 40px)', fontWeight: 300,
              color: '#0f172a', letterSpacing: '-0.01em',
              maxWidth: '26ch', lineHeight: 1.2,
            }}>
              Everything you need to<br /><strong style={{ fontWeight: 700 }}>measure and act</strong>
            </h2>
          </div>
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            style={{
              background: '#0d9488', color: '#f9fafb',
              border: 'none', padding: '12px 22px',
              fontFamily: 'Montserrat, sans-serif', fontWeight: 700,
              fontSize: 13, letterSpacing: '0.04em', cursor: 'pointer', borderRadius: 0,
            }}
          >
            Learn more
          </motion.button>
        </div>

        {/* Row 1 */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: 16, marginBottom: 16 }}>
          <div style={{ gridColumn: 'span 4' }}>
            <BounceCard style={{ background: '#f0fdf9', border: '1px solid rgba(13,148,136,0.15)' }}>
              <CardTitle dark>Extract</CardTitle>
              <CardDesc dark>Upload any PDF or CSV utility bill. Consumption, site, and billing period pulled automatically.</CardDesc>
              <ExtractPreview />
            </BounceCard>
          </div>
          <div style={{ gridColumn: 'span 8' }}>
            <BounceCard style={{ background: '#0d9488' }}>
              <CardTitle>Analyse</CardTitle>
              <CardDesc>Scope 1 & 2 footprint, anomaly detection, solar sizing, and forecasting from a single file upload.</CardDesc>
              <AnalysePreview />
            </BounceCard>
          </div>
        </div>

        {/* Row 2 */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: 16 }}>
          <div style={{ gridColumn: 'span 8' }}>
            <BounceCard style={{ background: '#0f172a' }}>
              <CardTitle>Recommend</CardTitle>
              <CardDesc>A tiered, cited action plan for cutting your footprint — matched to your sector and region.</CardDesc>
              <RecommendPreview />
            </BounceCard>
          </div>
          <div style={{ gridColumn: 'span 4' }}>
            <BounceCard style={{ background: '#f0fdf9', border: '1px solid rgba(13,148,136,0.15)' }}>
              <CardTitle dark>Report</CardTitle>
              <CardDesc dark>Audit-ready PDF with a fingerprint, scope tags, and full calculation trail.</CardDesc>
              <ReportPreview />
            </BounceCard>
          </div>
        </div>

      </div>
    </section>
  );
};