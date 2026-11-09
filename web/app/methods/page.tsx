"use client";
import { useState } from 'react';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import { useT } from '@/lib/i18n';
import { useApi } from '@/lib/hooks';
import { methodTitle, methodSummary } from '@/lib/method-name';
import type { MethodManifest } from '@/lib/api';
import { LoadingState } from '@/components/loading-indicator';
import { RequestError } from '@/components/request-error';
import s from '@/features/methods/tool-workspace.module.css';

export default function MethodsPage() {
  const t = useT();
  const { data, error, loading, reload } = useApi<MethodManifest[]>('/methods');
  const [kind, setKind] = useState('all');
  const [search, setSearch] = useState('');
  const filtered = (data || []).filter(v => (kind === 'all' || (v.implementation || 'python') === kind)
    && `${v.name} ${methodTitle(v,t)} ${v.description}`.toLowerCase().includes(search.trim().toLowerCase()));
  return <div className={s.page}>
    <div className={s.header}><div><h1>{t('Methods')}</h1><p>{t('Browse registered analysis instructions and Python functions.')}</p></div></div>
    {error && <RequestError title={t('Could not load the Method')} error={error} retry={reload} />}
    {loading && !data ? <LoadingState /> : data && <>
      <div className={s.toolbar}><label><input aria-label={t('Search Methods')} placeholder={t('Search by name or purpose')} value={search} onChange={e=>setSearch(e.target.value)} /></label>
        <select aria-label={t('Tool type')} value={kind} onChange={e=>setKind(e.target.value)}><option value="all">{t('All types')}</option><option value="skill">{t('Analysis instructions')}</option><option value="python">{t('Python functions')}</option></select></div>
      <div className={s.list}>{filtered.map(v=><Link key={v.name} className={s.row} href={`/methods/${encodeURIComponent(v.name)}`}><div><strong>{methodTitle(v,t)}</strong><small>{methodSummary(v,t)}</small></div><div className={s.badges}><span className={s.badge}>{t(v.implementation==='skill'?'Analysis instructions':'Python functions')}</span><span className={s.muted}>v{v.version}</span><ArrowRight size={16} aria-hidden="true" /></div></Link>)}
        {!filtered.length && <p className={s.empty}>{t(data.length?'No search results':'No Methods registered')}</p>}</div>
    </>}
  </div>;
}
