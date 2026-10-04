import { lazy, Suspense, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  Award,
  Briefcase,
  ChevronUp,
  Code2,
  Download,
  ExternalLink,
  GraduationCap,
  Menu,
  Mail,
  MapPin,
  Phone,
  Sparkles as SparkleIcon,
  Star,
  X,
} from 'lucide-react';

const HeroScene = lazy(() => import('./components/HeroScene.jsx'));

function App() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [activeSection, setActiveSection] = useState('experience');
  const [menuOpen, setMenuOpen] = useState(false);
  const [projectFilter, setProjectFilter] = useState('All');
  const [scrollProgress, setScrollProgress] = useState(0);
  const baseUrl = import.meta.env.BASE_URL;

  useEffect(() => {
    document.title = 'Rewa Prasad — Software Developer';
    const description = document.querySelector('meta[name="description"]');
    description?.setAttribute(
      'content',
      'Explore Rewa Prasad’s software development portfolio: Windchill, React, Java, enterprise workflows, and automation.'
    );

    const profileUrl = new URL(`${import.meta.env.BASE_URL}profile.json`, window.location.href);
    profileUrl.searchParams.set(
      'v',
      import.meta.env.VITE_PROFILE_VERSION || String(Date.now())
    );

    fetch(profileUrl)
      .then((res) => {
        if (!res.ok) throw new Error(`Profile request failed (${res.status})`);
        return res.json();
      })
      .then((data) => {
        setProfile(data);
        setLoading(false);
      })
      .catch((error) => {
        console.error('Unable to load portfolio profile:', error);
        setLoadError('The portfolio data could not be loaded. Please try again in a moment.');
        setLoading(false);
      });

    const updateProgress = () => {
      const scrollableHeight = document.documentElement.scrollHeight - window.innerHeight;
      setScrollProgress(scrollableHeight > 0 ? (window.scrollY / scrollableHeight) * 100 : 0);
    };
    updateProgress();
    window.addEventListener('scroll', updateProgress, { passive: true });

    return () => {
      window.removeEventListener('scroll', updateProgress);
    };
  }, []);

  useEffect(() => {
    if (!profile) return undefined;

    const sections = ['experience', 'projects', 'skills', 'contact']
      .map((id) => document.getElementById(id))
      .filter(Boolean);
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible) setActiveSection(visible.target.id);
      },
      { rootMargin: '-20% 0px -60% 0px', threshold: [0, 0.2, 0.5] }
    );
    sections.forEach((section) => observer.observe(section));

    return () => observer.disconnect();
  }, [profile]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-100">
        <div className="flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-5 py-3 text-sm text-slate-200 backdrop-blur-lg">
          <SparkleIcon className="h-4 w-4 animate-pulse text-violet-300" />
          Loading portfolio...
        </div>
      </div>
    );
  }

  if (loadError || !profile) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-950 px-6 text-center text-slate-100">
        <SparkleIcon className="h-8 w-8 text-violet-300" />
        <p className="max-w-md text-sm leading-6 text-slate-300">
          {loadError || 'Portfolio profile data is unavailable.'}
        </p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="rounded-full border border-white/15 bg-white/5 px-5 py-2 text-sm font-medium transition hover:bg-white/10"
        >
          Retry
        </button>
      </div>
    );
  }

  const navItems = [
    ['experience', 'Experience'],
    ['projects', 'Projects'],
    ['skills', 'Skills'],
    ['contact', 'Contact'],
  ];
  const projectFilters = ['All', 'Enterprise', 'React', 'JavaScript'];
  const filteredProjects = profile.projects.filter((project) => {
    if (projectFilter === 'All') return true;
    if (projectFilter === 'Enterprise') return Boolean(project.company);
    return project.stack.some((item) => item.toLowerCase().includes(projectFilter.toLowerCase()));
  });

  return (
    <div className="min-h-screen bg-slate-950 text-white selection:bg-violet-500/40">
      <div className="fixed left-0 right-0 top-0 z-50 h-[2px] bg-white/5">
        <div
          className="h-full bg-gradient-to-r from-violet-500 via-indigo-400 to-cyan-300 transition-[width] duration-150"
          style={{ width: `${scrollProgress}%` }}
        />
      </div>
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_top,_rgba(129,140,248,0.16),_transparent_35%),linear-gradient(180deg,_rgba(15,23,42,0.9),_rgba(2,6,23,1))]" />

      <main className="relative mx-auto max-w-7xl px-4 pb-20 pt-5 sm:px-6 lg:px-8">
        <header className="sticky top-3 z-40 mb-8 flex items-center justify-between rounded-2xl border border-white/10 bg-slate-950/75 px-4 py-3 shadow-glow backdrop-blur-2xl sm:rounded-full">
          <a href="#top" aria-label="Back to top" className="flex items-center gap-3">
            <img src={`${baseUrl}rewa-prasad-office.jpg`} alt="" className="h-10 w-10 rounded-full border border-white/20 object-cover object-top" />
            <div>
              <p className="text-[10px] uppercase tracking-[0.28em] text-violet-200/80">Portfolio / 2026</p>
              <p className="text-sm font-medium text-slate-200">{profile.name}</p>
            </div>
          </a>
          <nav aria-label="Main navigation" className="hidden items-center gap-1 md:flex">
            {navItems.map(([id, label]) => (
              <a
                key={id}
                href={`#${id}`}
                aria-current={activeSection === id ? 'location' : undefined}
                className={`rounded-full px-4 py-2 text-sm transition ${
                  activeSection === id
                    ? 'bg-white/10 text-white'
                    : 'text-slate-400 hover:bg-white/5 hover:text-white'
                }`}
              >
                {label}
              </a>
            ))}
            <a href={`${baseUrl}Rewa-Prasad-Resume.pdf`} download className="ml-2 inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-100">
              <Download className="h-4 w-4" />
              Resume
            </a>
          </nav>
          <button
            type="button"
            className="rounded-full border border-white/10 p-2 text-slate-200 md:hidden"
            aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
          >
            {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
          {menuOpen && (
            <nav aria-label="Mobile navigation" className="absolute left-0 right-0 top-[calc(100%+0.5rem)] grid gap-1 rounded-2xl border border-white/10 bg-slate-950/95 p-3 shadow-2xl backdrop-blur-2xl md:hidden">
              {navItems.map(([id, label]) => (
                <a key={id} href={`#${id}`} onClick={() => setMenuOpen(false)} className="rounded-xl px-4 py-3 text-sm text-slate-200 hover:bg-white/10">
                  {label}
                </a>
              ))}
              <a href={`${baseUrl}Rewa-Prasad-Resume.pdf`} download className="inline-flex items-center gap-2 rounded-xl px-4 py-3 text-sm text-cyan-200 hover:bg-white/10">
                <Download className="h-4 w-4" />
                Download resume
              </a>
            </nav>
          )}
        </header>

        <section id="top" className="grid scroll-mt-28 items-center gap-8 pb-14 pt-6 lg:grid-cols-[1.2fr_0.8fr]">
          <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-violet-400/30 bg-violet-500/10 px-3 py-1 text-xs font-medium tracking-[0.2em] text-violet-200 uppercase">
              <Code2 className="h-3.5 w-3.5" />
              Engineering useful digital experiences
            </div>
            <h1 className="max-w-xl text-4xl font-black leading-tight tracking-[-0.06em] text-white sm:text-5xl lg:text-7xl">
              {profile.role}
            </h1>
            <p className="mt-6 max-w-2xl text-base leading-8 text-slate-300 sm:text-lg">
              {profile.headline}
            </p>
            <div className="mt-8 flex flex-wrap gap-4">
              <a
                href="#projects"
                className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-violet-600 to-indigo-500 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-500/30 transition hover:scale-[1.02]"
              >
                View projects
                <ArrowRight className="h-4 w-4" />
              </a>
              <a
                href={profile.contact.linkedin}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-5 py-3 text-sm font-semibold text-slate-200 transition hover:border-violet-400/40 hover:bg-white/10"
              >
                LinkedIn
                <ExternalLink className="h-4 w-4" />
              </a>
              <a
                href={`${baseUrl}Rewa-Prasad-Resume.pdf`}
                download
                className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-5 py-3 text-sm font-semibold text-slate-200 transition hover:border-cyan-300/40 hover:bg-white/10"
              >
                Download CV
                <Download className="h-4 w-4" />
              </a>
            </div>

            <div className="mt-10 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {profile.metrics.map((item) => (
                <div key={item.label} className="rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur-lg">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{item.label}</p>
                  <p className="mt-3 text-lg font-semibold text-white">{item.value}</p>
                </div>
              ))}
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.7, delay: 0.15 }} className="relative">
            <div className="absolute inset-0 -z-10 rounded-[2rem] bg-gradient-to-br from-violet-500/20 via-cyan-500/10 to-slate-900 blur-2xl" />
            <div className="overflow-hidden rounded-[2rem] border border-white/10 bg-slate-900/70 p-3 shadow-[0_20px_80px_rgba(76,29,149,0.55)] backdrop-blur-xl">
              <div className="relative h-[440px] overflow-hidden rounded-[1.5rem] border border-white/10 bg-slate-950/80">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(124,58,237,0.25),transparent_20%),radial-gradient(circle_at_80%_12%,rgba(34,211,238,0.2),transparent_18%)]" />
                <div className="absolute left-4 top-4 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] uppercase tracking-[0.25em] text-slate-300">
                  live system
                </div>
                <div className="absolute inset-0 opacity-40" aria-hidden="true">
                  <Suspense fallback={null}>
                    <HeroScene />
                  </Suspense>
                </div>
                <div className="relative z-10 flex h-full items-center justify-center px-6 pt-8">
                  <div className="relative rounded-[2rem] bg-gradient-to-br from-violet-400 via-cyan-300 to-violet-600 p-[2px] shadow-[0_20px_70px_rgba(76,29,149,0.65)]">
                    <img
                      src={`${baseUrl}rewa-prasad-office.jpg`}
                      alt="Rewa Prasad"
                      className="h-[400px] w-[300px] max-w-full rounded-[calc(2rem-2px)] object-cover object-top"
                    />
                    <div className="absolute inset-x-0 bottom-0 rounded-b-[calc(2rem-2px)] bg-gradient-to-t from-slate-950/90 via-slate-950/45 to-transparent px-5 pb-5 pt-14">
                      <p className="text-lg font-semibold text-white">{profile.name}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.2em] text-cyan-200">{profile.role}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </section>

        <section className="mb-10 rounded-[2rem] border border-white/10 bg-white/5 p-6 backdrop-blur-xl sm:p-8">
          <div className="flex items-center gap-3">
            <SparkleIcon className="h-5 w-5 text-violet-300" />
            <h2 className="text-xl font-semibold text-white">Profile Summary</h2>
          </div>
          <p className="mt-4 max-w-5xl text-base leading-8 text-slate-300">{profile.summary}</p>
        </section>

        <section id="experience" className="mb-10 scroll-mt-28">
          <div className="mb-6 flex items-center gap-3">
            <Briefcase className="h-5 w-5 text-cyan-300" />
            <h2 className="text-2xl font-semibold text-white">Experience</h2>
          </div>

          <div className="space-y-6">
            {profile.experiences.map((job, index) => (
              <motion.article
                key={job.company}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.15 }}
                transition={{ delay: index * 0.08 }}
                className="rounded-[2rem] border border-white/10 bg-slate-900/70 p-6 shadow-[0_10px_30px_rgba(15,23,42,0.55)] transition-colors hover:border-violet-300/25"
              >
                <div className="flex flex-col gap-4 border-b border-white/10 pb-4 md:flex-row md:items-center md:justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-[0.24em] text-violet-200/80">{job.type}</p>
                    <h3 className="mt-2 text-2xl font-bold text-white">{job.role}</h3>
                    <p className="mt-1 text-base text-slate-300">
                      {job.company} • {job.location}
                    </p>
                  </div>
                  <div className="rounded-full border border-cyan-400/30 bg-cyan-500/10 px-3 py-1 text-xs font-medium text-cyan-100">
                    {job.duration}
                  </div>
                </div>
                <ul className="mt-5 space-y-3 text-slate-300">
                  {job.highlights.map((point) => (
                    <li key={point} className="flex gap-3">
                      <span className="mt-2 h-2 w-2 flex-shrink-0 rounded-full bg-gradient-to-r from-violet-400 to-cyan-400" />
                      <span className="leading-7">{point}</span>
                    </li>
                  ))}
                </ul>
              </motion.article>
            ))}
          </div>
        </section>

        <section id="projects" className="mb-10 scroll-mt-28">
          <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div className="flex items-center gap-3">
              <Star className="h-5 w-5 text-violet-300" />
              <div>
                <h2 className="text-2xl font-semibold text-white">Featured Projects</h2>
                <p className="mt-1 text-sm text-slate-400">A selection of enterprise and personal work</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2" aria-label="Filter projects">
              {projectFilters.map((filter) => (
                <button
                  key={filter}
                  type="button"
                  aria-pressed={projectFilter === filter}
                  onClick={() => setProjectFilter(filter)}
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                    projectFilter === filter
                      ? 'border-violet-300/50 bg-violet-400/15 text-violet-100'
                      : 'border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/25 hover:text-white'
                  }`}
                >
                  {filter}
                </button>
              ))}
            </div>
          </div>

          <div className="columns-1 gap-6 xl:columns-2">
            {filteredProjects.map((project, index) => (
              <motion.article
                key={project.name}
                initial={{ opacity: 0, y: 18 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.12 }}
                transition={{ delay: index * 0.08 }}
                className="group mb-6 inline-flex w-full break-inside-avoid flex-col rounded-[2rem] border border-white/10 bg-slate-900/70 p-6 shadow-[0_10px_30px_rgba(15,23,42,0.55)] transition-colors hover:border-violet-300/30"
              >
                <div className="mb-4 flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-violet-200/80">{project.company || 'Personal Build'}</p>
                    <h3 className="mt-2 text-xl font-bold text-white">{project.name}</h3>
                  </div>
                  {project.link && (
                    <a href={project.link} target="_blank" rel="noreferrer" className="rounded-full border border-white/10 bg-white/5 p-2 text-slate-200 transition hover:border-violet-400/40 hover:text-white">
                      <ExternalLink className="h-4 w-4" />
                    </a>
                  )}
                </div>
                {project.period && <p className="mb-4 text-sm text-cyan-200">{project.period}</p>}
                <p className="mb-5 leading-7 text-slate-300">{project.description}</p>

                <div className="mb-5 flex flex-wrap gap-2">
                  {project.stack.map((tag) => (
                    <span key={tag} className="rounded-full border border-violet-400/30 bg-violet-500/10 px-2.5 py-1 text-xs text-violet-100">
                      {tag}
                    </span>
                  ))}
                </div>

                <ul className="space-y-3 text-sm leading-7 text-slate-300">
                  {project.achievements.map((achievement) => (
                    <li key={achievement} className="flex gap-3">
                      <span className="mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-gradient-to-r from-cyan-400 to-violet-500" />
                      <span>{achievement}</span>
                    </li>
                  ))}
                </ul>
              </motion.article>
            ))}
          </div>
        </section>

        <section id="skills" className="mb-10 grid scroll-mt-28 gap-6 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="rounded-[2rem] border border-white/10 bg-slate-900/70 p-6">
            <div className="mb-6 flex items-center gap-3">
              <Code2 className="h-5 w-5 text-violet-300" />
              <h2 className="text-2xl font-semibold text-white">Skill Stack</h2>
            </div>

            <div className="grid items-start gap-5 md:grid-cols-2">
              {Object.entries(profile.skills).map(([group, items]) => (
                <div key={group} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="mb-3 text-xs uppercase tracking-[0.2em] text-slate-400">{group}</p>
                  <div className="flex flex-wrap gap-2">
                    {items.map((item) => (
                      <span key={item} className="rounded-full border border-cyan-400/20 bg-cyan-500/10 px-2.5 py-1 text-xs text-cyan-100">
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-6 rounded-[2rem] border border-white/10 bg-slate-900/70 p-6">
            <div className="flex items-center gap-3">
              <GraduationCap className="h-5 w-5 text-cyan-300" />
              <h2 className="text-2xl font-semibold text-white">Education</h2>
            </div>
            <div className="space-y-4">
              {profile.education.map((edu) => (
                <div key={edu.school} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-sm font-semibold text-white">{edu.degree || 'Course'}</p>
                  <p className="mt-1 text-slate-300">{edu.school}</p>
                  {edu.field && <p className="mt-1 text-sm text-slate-400">{edu.field}</p>}
                  <p className="mt-2 text-xs uppercase tracking-[0.18em] text-violet-200/80">{edu.period}</p>
                  {edu.gpa && <p className="mt-2 text-sm text-cyan-200">{edu.gpa}</p>}
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mb-10 grid gap-6 lg:grid-cols-2">
          <div className="rounded-[2rem] border border-white/10 bg-slate-900/70 p-6">
            <div className="mb-5 flex items-center gap-3">
              <Award className="h-5 w-5 text-violet-300" />
              <h2 className="text-2xl font-semibold text-white">Certifications</h2>
            </div>
            <ul className="space-y-3 text-slate-300">
              {profile.certifications.map((item) => (
                <li key={item} className="flex gap-3">
                  <span className="mt-2 h-2 w-2 rounded-full bg-gradient-to-r from-violet-400 to-indigo-500" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-[2rem] border border-white/10 bg-slate-900/70 p-6">
            <div className="mb-5 flex items-center gap-3">
              <Star className="h-5 w-5 text-cyan-300" />
              <h2 className="text-2xl font-semibold text-white">Awards</h2>
            </div>
            <ul className="space-y-3 text-slate-300">
              {profile.awards.map((item) => (
                <li key={item} className="flex gap-3">
                  <span className="mt-2 h-2 w-2 rounded-full bg-gradient-to-r from-cyan-400 to-indigo-500" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <footer id="contact" className="scroll-mt-28 rounded-[2rem] border border-white/10 bg-gradient-to-r from-violet-500/10 via-slate-900/80 to-cyan-500/10 p-6 backdrop-blur-xl">
          <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-violet-200/80">Contact</p>
              <h2 className="mt-2 text-3xl font-bold text-white">Let’s build something exceptional.</h2>
            </div>
            <div className="grid gap-3 text-sm text-slate-200 sm:text-right">
              <a href={`mailto:${profile.contact.email}`} className="inline-flex items-center gap-2 justify-start sm:justify-end hover:text-white">
                <Mail className="h-4 w-4" />
                {profile.contact.email}
              </a>
              <a href={`tel:${profile.contact.phone.replace(/\s+/g, '')}`} className="inline-flex items-center gap-2 justify-start sm:justify-end hover:text-white">
                <Phone className="h-4 w-4" />
                {profile.contact.phone}
              </a>
              <div className="inline-flex items-center gap-2 justify-start sm:justify-end text-slate-200">
                <MapPin className="h-4 w-4" />
                {profile.contact.location}
              </div>
            </div>
          </div>
        </footer>
        <p className="mt-8 text-center text-xs tracking-wide text-slate-500">
          Designed and developed by {profile.name} · Pune, India
        </p>
      </main>
      {scrollProgress > 8 && (
        <button
          type="button"
          aria-label="Back to top"
          onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
          className="fixed bottom-5 right-5 z-40 rounded-full border border-white/15 bg-slate-900/80 p-3 text-slate-200 shadow-xl backdrop-blur transition hover:border-violet-300/40 hover:text-white"
        >
          <ChevronUp className="h-5 w-5" />
        </button>
      )}
    </div>
  );
}

export default App;
