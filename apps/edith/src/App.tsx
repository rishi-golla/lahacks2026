import { motion, useInView } from 'framer-motion'
import { ArrowRight, Check } from 'lucide-react'
import { useRef } from 'react'

const heroVideoUrl =
  'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260405_170732_8a9ccda6-5cff-4628-b164-059c500a2b41.mp4'

const featureVideoUrl =
  'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260406_133058_0504132a-0cf3-4450-a370-8ea3b05c95d4.mp4'

const navItems = ['Our story', 'Collective', 'Workshops', 'Programs', 'Inquiries']

const featureCards = [
  {
    number: '01',
    title: 'Project Storyboard.',
    image:
      'https://images.higgs.ai/?default=1&output=webp&url=https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20260405_171918_4a5edc79-d78f-4637-ac8b-53c43c220606.png&w=1280&q=85',
    items: [
      'Generate boards for every beat with cinematic continuity.',
      'Lock camera logic, palette, and composition before production.',
      'Pressure-test pacing while the story is still malleable.',
      'Share visual intent with collaborators in a readable sequence.',
    ],
  },
  {
    number: '02',
    title: 'Smart Critiques.',
    image:
      'https://images.higgs.ai/?default=1&output=webp&url=https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20260405_171741_ed9845ab-f5b2-4018-8ce7-07cc01823522.png&w=1280&q=85',
    items: [
      'Receive AI analysis shaped like creative notes, not reports.',
      'Spot weak scenes, uneven rhythm, and visual drift fast.',
      'Bridge review across your tools without breaking flow.',
    ],
  },
  {
    number: '03',
    title: 'Immersion Capsule.',
    image:
      'https://images.higgs.ai/?default=1&output=webp&url=https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20260405_171809_f56666dc-c099-4778-ad82-9ad4f209567b.png&w=1280&q=85',
    items: [
      'Silence notifications when the work enters deep-focus mode.',
      'Shape atmosphere with ambient soundscapes tuned to the scene.',
      'Sync schedules so immersion becomes a ritual, not an accident.',
    ],
  },
] as const

const ease: [number, number, number, number] = [0.16, 1, 0.3, 1]

type Segment = {
  text: string
  className?: string
}

type WordsPullUpProps = {
  text: string
  className?: string
  showAsterisk?: boolean
}

type WordsPullUpMultiStyleProps = {
  segments: readonly Segment[]
  className?: string
}

type FeatureCardProps = {
  number: string
  title: string
  image: string
  items: readonly string[]
  index: number
}

function WordsPullUp({ text, className, showAsterisk = false }: WordsPullUpProps) {
  const ref = useRef<HTMLSpanElement | null>(null)
  const inView = useInView(ref, { once: true, margin: '-100px' })
  const words = text.split(' ')

  return (
    <span ref={ref} className={`inline-flex flex-wrap ${className ?? ''}`}>
      {words.map((word, index) => {
        const isLastWord = index === words.length - 1

        return (
          <span key={`${word}-${index}`} className="overflow-hidden pb-[0.12em]">
            <motion.span
              className="relative inline-block"
              initial={{ y: 20, opacity: 0 }}
              animate={inView ? { y: 0, opacity: 1 } : { y: 20, opacity: 0 }}
              transition={{ duration: 0.8, delay: index * 0.08, ease }}
            >
              {word}
              {showAsterisk && isLastWord ? (
                <span className="absolute -right-[0.3em] top-[0.65em] text-[0.31em]">*</span>
              ) : null}
            </motion.span>
            {index < words.length - 1 ? <span>&nbsp;</span> : null}
          </span>
        )
      })}
    </span>
  )
}

function WordsPullUpMultiStyle({ segments, className }: WordsPullUpMultiStyleProps) {
  const ref = useRef<HTMLDivElement | null>(null)
  const inView = useInView(ref, { once: true, margin: '-100px' })
  const words = segments.flatMap((segment) =>
    segment.text.split(' ').map((word) => ({
      word,
      className: segment.className ?? '',
    })),
  )

  return (
    <div ref={ref} className={`inline-flex flex-wrap justify-center ${className ?? ''}`}>
      {words.map(({ word, className: wordClass }, index) => (
        <span key={`${word}-${index}`} className="overflow-hidden pb-[0.12em]">
          <motion.span
            className={`inline-block ${wordClass}`}
            initial={{ y: 20, opacity: 0 }}
            animate={inView ? { y: 0, opacity: 1 } : { y: 20, opacity: 0 }}
            transition={{ duration: 0.8, delay: index * 0.08, ease }}
          >
            {word}
          </motion.span>
          {index < words.length - 1 ? <span>&nbsp;</span> : null}
        </span>
      ))}
    </div>
  )
}

function FeatureCard({ number, title, image, items, index }: FeatureCardProps) {
  const ref = useRef<HTMLDivElement | null>(null)
  const inView = useInView(ref, { once: true, margin: '-100px' })

  return (
    <motion.article
      ref={ref}
      initial={{ opacity: 0, scale: 0.95, y: 18 }}
      animate={inView ? { opacity: 1, scale: 1, y: 0 } : { opacity: 0, scale: 0.95, y: 18 }}
      transition={{ duration: 0.85, delay: index * 0.15, ease: [0.22, 1, 0.36, 1] }}
      className="flex h-full min-h-[280px] flex-col justify-between rounded-[1.75rem] bg-[#212121] p-5 sm:p-6"
    >
      <div className="space-y-5">
        <img src={image} alt="" className="h-10 w-10 rounded-xl object-cover sm:h-12 sm:w-12" />
        <div className="space-y-1">
          <p className="text-[10px] uppercase tracking-[0.3em] text-primary/65">{number}</p>
          <h3 style={{ color: '#E1E0CC' }} className="text-xl sm:text-2xl">
            {title}
          </h3>
        </div>
        <ul className="space-y-3">
          {items.map((item) => (
            <li key={item} className="flex items-start gap-3">
              <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              <span className="text-sm leading-5 text-gray-400">{item}</span>
            </li>
          ))}
        </ul>
      </div>

      <button
        type="button"
        className="mt-8 inline-flex items-center gap-2 self-start text-sm text-primary transition-transform hover:translate-x-1"
      >
        Learn more
        <ArrowRight className="-rotate-45" size={16} />
      </button>
    </motion.article>
  )
}

export default function App() {
  return (
    <main className="bg-black text-primary">
      <section className="h-screen bg-black p-4 md:p-6">
        <div className="relative h-full overflow-hidden rounded-2xl md:rounded-[2rem]">
          <video
            autoPlay
            loop
            muted
            playsInline
            className="absolute inset-0 h-full w-full object-cover"
            src={heroVideoUrl}
          />
          <div className="noise-overlay pointer-events-none absolute inset-0 opacity-[0.7] mix-blend-overlay" />
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-black/30 via-transparent to-black/60" />

          <div className="absolute left-1/2 top-0 z-20 -translate-x-1/2">
            <nav className="rounded-b-2xl bg-black px-4 py-2 md:rounded-b-3xl md:px-8">
              <ul className="flex items-center gap-3 sm:gap-6 md:gap-12 lg:gap-14">
                {navItems.map((item) => (
                  <li key={item}>
                    <a
                      href="#"
                      className="text-[10px] sm:text-xs md:text-sm transition-colors"
                      style={{ color: 'rgba(225, 224, 204, 0.8)' }}
                      onMouseEnter={(event) => {
                        event.currentTarget.style.color = '#E1E0CC'
                      }}
                      onMouseLeave={(event) => {
                        event.currentTarget.style.color = 'rgba(225, 224, 204, 0.8)'
                      }}
                    >
                      {item}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          </div>

          <div className="absolute bottom-0 left-0 right-0 z-10 p-4 sm:p-6 md:p-8 lg:p-10">
            <div className="grid items-end gap-6 md:grid-cols-12">
              <div className="md:col-span-8">
                <WordsPullUp
                  text="Edith"
                  showAsterisk
                  className="text-[26vw] font-medium leading-[0.85] tracking-[-0.045em] sm:text-[24vw] md:text-[22vw] lg:text-[20vw] xl:text-[19vw] 2xl:text-[20vw]"
                />
              </div>

              <div className="space-y-5 md:col-span-4 md:pb-6">
                <motion.p
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.8, delay: 0.5, ease }}
                  className="max-w-sm text-xs leading-[1.2] text-primary/70 sm:text-sm md:text-base"
                >
                  Edith is a worldwide network of visual artists, filmmakers and storytellers
                  bound not by place, status or labels but by passion and hunger to unlock
                  potential through our unique perspectives.
                </motion.p>

                <motion.button
                  type="button"
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.8, delay: 0.7, ease }}
                  className="group inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-black transition-all hover:gap-3 sm:text-base"
                >
                  Join the lab
                  <span className="flex h-9 w-9 items-center justify-center rounded-full bg-black transition-transform group-hover:scale-110 sm:h-10 sm:w-10">
                    <ArrowRight className="h-4 w-4 text-primary" />
                  </span>
                </motion.button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="relative min-h-screen overflow-hidden bg-black px-4 py-24 sm:px-6 md:px-8">
        <div className="bg-noise pointer-events-none absolute inset-0 opacity-[0.15]" />
        <div className="relative mx-auto max-w-7xl">
          <div className="mb-12 space-y-3 text-center">
            <div
              style={{ color: '#E1E0CC' }}
              className="text-xl font-normal sm:text-2xl md:text-3xl lg:text-4xl"
            >
              <WordsPullUpMultiStyle
                segments={[{ text: 'Studio-grade workflows for visionary creators.' }]}
              />
            </div>
            <div className="text-xl font-normal text-gray-500 sm:text-2xl md:text-3xl lg:text-4xl">
              <WordsPullUpMultiStyle
                segments={[{ text: 'Built for pure vision. Powered by art.', className: 'text-gray-500' }]}
              />
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2 lg:h-[480px] lg:grid-cols-4 lg:gap-1">
            <motion.article
              initial={{ opacity: 0, scale: 0.95, y: 18 }}
              whileInView={{ opacity: 1, scale: 1, y: 0 }}
              viewport={{ once: true, margin: '-100px' }}
              transition={{ duration: 0.85, ease: [0.22, 1, 0.36, 1] }}
              className="relative min-h-[280px] overflow-hidden rounded-[1.75rem]"
            >
              <video
                autoPlay
                loop
                muted
                playsInline
                className="absolute inset-0 h-full w-full object-cover"
                src={featureVideoUrl}
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />
              <div className="absolute bottom-0 left-0 right-0 p-5 sm:p-6">
                <p style={{ color: '#E1E0CC' }} className="text-lg sm:text-xl">
                  Your creative canvas.
                </p>
              </div>
            </motion.article>

            {featureCards.map((card, index) => (
              <FeatureCard key={card.title} {...card} index={index + 1} />
            ))}
          </div>
        </div>
      </section>
    </main>
  )
}
