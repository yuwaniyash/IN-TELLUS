import { ChevronRight } from 'lucide-react';
import { ParticleRing } from './ParticleRing';
import { CardSwap, Card } from './CardSwap';

export function HeroLanding({ onGetStarted, onLearnMore }) {
  return (
    <div style={{
      position: 'relative',
      minHeight: '100vh',
      background: '#f9fafb',
      overflow: 'hidden',
      fontFamily: 'Montserrat, sans-serif',
    }}>

      {/* ParticleRing — fills entire hero behind content */}
      <div style={{
        position: 'absolute',
        top: 0, left: 0, right: 0, bottom: 0,
        width: '100%', height: '100%',
        zIndex: 0,
        opacity: 0.35,        /* mint, non-obstructive */
        pointerEvents: 'none', /* don't block clicks */
      }}>
        <ParticleRing />
      </div>

      {/* Spacer for fixed nav */}
      <div style={{ height: 80 }} />

      {/* Content row — sits above particle canvas */}
      <div style={{
        position: 'relative',
        zIndex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        minHeight: 'calc(100vh - 80px)',
        padding: '80px 64px 80px',
        gap: 64,
        flexWrap: 'wrap',
      }}>

        {/* Left: headline + CTAs */}
        <div style={{ flex: '1 1 480px', maxWidth: 580 }}>
          <p style={{
            fontSize: 11, fontWeight: 700, letterSpacing: '0.16em',
            color: '#0d9488', marginBottom: 28,
          }}>
            SUSTAINABILITY INTELLIGENCE
          </p>

          <h1 style={{
            fontSize: 'clamp(36px, 5vw, 64px)',
            fontWeight: 300, lineHeight: 1.08,
            color: '#0f172a', letterSpacing: '-0.02em',
            marginBottom: 24,
          }}>
            Know your carbon.<br />
            <strong style={{ fontWeight: 700, color: '#0d9488' }}>Act on it.</strong>
          </h1>

          <p style={{
            fontSize: 16, color: 'rgba(15,23,42,0.5)',
            lineHeight: 1.7, maxWidth: '44ch', marginBottom: 48,
          }}>
            Upload any utility bill. IN-TELLUS extracts your consumption data,
            calculates your emissions footprint, and hands you a concrete action
            plan — in minutes.
          </p>

          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
            <button
              onClick={onGetStarted}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 8,
                background: '#0d9488', color: '#f9fafb',
                border: 'none', padding: '13px 26px',
                fontFamily: 'Montserrat, sans-serif', fontWeight: 700,
                fontSize: 13, letterSpacing: '0.04em', cursor: 'pointer',
                transition: 'opacity 0.15s', borderRadius: 0,
              }}
              onMouseOver={e => e.currentTarget.style.opacity = '0.85'}
              onMouseOut={e => e.currentTarget.style.opacity = '1'}
            >
              Get started <ChevronRight size={15} />
            </button>
            <button
              onClick={onLearnMore}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 8,
                background: 'transparent', color: '#0f172a',
                border: '1px solid rgba(15,23,42,0.2)', padding: '13px 26px',
                fontFamily: 'Montserrat, sans-serif', fontWeight: 600,
                fontSize: 13, letterSpacing: '0.04em', cursor: 'pointer',
                transition: 'border-color 0.15s, color 0.15s', borderRadius: 0,
              }}
              onMouseOver={e => { e.currentTarget.style.borderColor = '#0d9488'; e.currentTarget.style.color = '#0d9488'; }}
              onMouseOut={e => { e.currentTarget.style.borderColor = 'rgba(15,23,42,0.2)'; e.currentTarget.style.color = '#0f172a'; }}
            >
              See how it works
            </button>
          </div>
        </div>

        {/* Right: CardSwap */}
        <div style={{
          flex: '0 0 auto',
          position: 'relative',
          width: 500, height: 420,
          zIndex: 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginTop: 60,   /* push down to align with mid-hero */
        }}>
          <CardSwap
            width={420} height={300}
            cardDistance={55} verticalDistance={60}
            delay={4000} pauseOnHover={true}
            skewAmount={4} easing="elastic"
          >
            <Card style={{
              background: '#ffffff',
              border: '1px solid rgba(13,148,136,0.3)',
              boxShadow: '0 8px 40px rgba(13,148,136,0.15), 0 2px 12px rgba(15,23,42,0.1)',
              borderRadius: 16,
              display: 'flex', flexDirection: 'column',
              alignItems: 'flex-start', justifyContent: 'space-between',
              padding: 36,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.14em', color: '#0d9488' }}>SCOPE 1 + 2</p>
                <span style={{ fontSize: 10, fontWeight: 600, background: 'rgba(13,148,136,0.1)', color: '#0d9488', padding: '3px 10px', borderRadius: 999 }}>Nov 2024</span>
              </div>
              <div>
                <p style={{ fontSize: 48, fontWeight: 200, color: '#0f172a', letterSpacing: '-0.03em', lineHeight: 1, marginBottom: 6 }}>
                  2,840
                </p>
                <p style={{ fontSize: 13, fontWeight: 500, color: 'rgba(15,23,42,0.45)' }}>kg CO₂e · Colombo South</p>
              </div>
              <div style={{ width: '100%', height: 4, background: 'rgba(13,148,136,0.1)', borderRadius: 999, overflow: 'hidden' }}>
                <div style={{ width: '68%', height: '100%', background: '#0d9488', borderRadius: 999 }} />
              </div>
            </Card>

            <Card style={{
              background: '#f0fdf9',
              border: '1px solid rgba(13,148,136,0.3)',
              boxShadow: '0 8px 40px rgba(13,148,136,0.12), 0 2px 12px rgba(15,23,42,0.08)',
              borderRadius: 16,
              display: 'flex', flexDirection: 'column',
              alignItems: 'flex-start', justifyContent: 'space-between',
              padding: 36,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.14em', color: '#0d9488' }}>SOLAR POTENTIAL</p>
                <span style={{ fontSize: 10, fontWeight: 600, background: 'rgba(13,148,136,0.15)', color: '#0d9488', padding: '3px 10px', borderRadius: 999 }}>☀ Recommended</span>
              </div>
              <div>
                <p style={{ fontSize: 48, fontWeight: 200, color: '#0f172a', letterSpacing: '-0.03em', lineHeight: 1, marginBottom: 6 }}>
                  18 <span style={{ fontSize: 18, fontWeight: 300 }}>kWp</span>
                </p>
                <p style={{ fontSize: 13, fontWeight: 500, color: 'rgba(15,23,42,0.45)' }}>Payback 4.2 yrs · 74% offset</p>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                {['Solar sizing', 'ROI calc', 'Region-matched'].map(tag => (
                  <span key={tag} style={{ fontSize: 11, fontWeight: 600, color: '#0d9488', background: 'rgba(13,148,136,0.1)', padding: '4px 10px', borderRadius: 999 }}>{tag}</span>
                ))}
              </div>
            </Card>

            <Card style={{
              background: '#ffffff',
              border: '1px solid rgba(220,38,38,0.2)',
              boxShadow: '0 8px 40px rgba(220,38,38,0.08), 0 2px 12px rgba(15,23,42,0.08)',
              borderRadius: 16,
              display: 'flex', flexDirection: 'column',
              alignItems: 'flex-start', justifyContent: 'space-between',
              padding: 36,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.14em', color: '#26b1b8' }}>⚠ ANOMALY DETECTED</p>
                <span style={{ fontSize: 10, fontWeight: 600, background: 'rgba(220,38,38,0.08)', color: '#20b9a5', padding: '3px 10px', borderRadius: 999 }}>Oct 2024</span>
              </div>
              <div>
                <p style={{ fontSize: 28, fontWeight: 600, color: '#0f172a', lineHeight: 1.25, marginBottom: 6 }}>
                  38% above baseline
                </p>
                <p style={{ fontSize: 13, fontWeight: 500, color: 'rgba(15,23,42,0.45)' }}>Kandy Branch · Electricity</p>
              </div>
              <div style={{ width: '100%', height: 6, background: 'rgba(220,38,38,0.08)', borderRadius: 999, overflow: 'hidden' }}>
                <div style={{ width: '38%', height: '100%', background: '#1c9da6', borderRadius: 999 }} />
              </div>
            </Card>
          </CardSwap>
        </div>

      </div>
    </div>
  );
}