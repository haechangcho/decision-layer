"use client";
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { useApi } from '@/lib/hooks';
import { useT } from '@/lib/i18n';
import { methodTitle } from '@/lib/method-name';
import type { MethodManifest } from '@/lib/api';
import { WorkspaceTabs } from '@/components/workspace-tabs';
import { LoadingState } from '@/components/loading-indicator';
import { RequestError } from '@/components/request-error';
import { MethodAssetEditor } from '@/features/methods/method-asset-editor';
import { PythonInputContract } from '@/features/methods/python-input-contract';
import { MethodExecutions } from '@/features/methods/method-executions';
import s from '@/features/methods/tool-workspace.module.css';

export default function MethodPage() {
  const t=useT();
  const {name}=useParams<{name:string}>();
  const {data:method,error,reload}=useApi<MethodManifest>(`/methods/${encodeURIComponent(name)}`);
  const [view,setView]=useState('overview');
  useEffect(()=>setView('overview'),[name]);
  const skill=method?.implementation==='skill';
  return <div className={s.page}>
    <Link className={s.back} href="/methods"><ArrowLeft size={15}/>{t('Methods')}</Link>
    {error&&<RequestError title={t('Could not load the Method')} error={error} retry={reload}/>}
    {!method?!error&&<LoadingState/>:<>
      <div className={s.header}><div><h1>{methodTitle(method,t)}</h1><p>{t(method.description)}</p><div className={s.meta}><span className={s.badge}>{t(skill?'Analysis instructions':'Python functions')}</span><span className={s.muted}>v{method.version}</span></div></div></div>
      <WorkspaceTabs id="method" label={t('Method information')} value={view} onChange={setView} items={[
        {value:'overview',label:t('Use tool')},{value:'implementation',label:t(skill?'Analysis instructions':'Python code')},{value:'executions',label:t('Runs')},
      ]}/>
      <div role="tabpanel" id={`method-panel-${view}`} aria-labelledby={`method-tab-${view}`}>
        {view==='overview'&&<>
          {(!skill||method.agent_executable)&&<section className={s.panel}><h2>{t(skill?'Run with AI':'Test with real data')}</h2><p className={s.muted}>{t(skill?'Ask your connected AI to run this Method. Queries and results are recorded.':'Choose a metric and dates to test. Results are saved as a Run.')}</p><div className={s.actions}><Link className={s.button} href={`/recipes/new?method=${encodeURIComponent(name)}`}>{t(skill?'Create analysis procedure':'Choose inputs and test')}</Link></div></section>}
          {!skill&&<section className={s.panel}><h2>{t('Required data')}</h2><PythonInputContract method={method}/>
            {!Object.keys(method.data_inputs??{}).length&&<dl className={s.meta}>{Object.entries(method.roles).map(([key,role])=><div key={key}><dt>{role.label||key}{role.required?' *':''}</dt><dd>{role.description||(role.accepted_kinds??[role.kind]).join(' / ')}</dd></div>)}</dl>}
            {!!Object.keys(method.parameters).length&&<><h3>{t('Calculation options')}</h3><dl>{Object.entries(method.parameters).map(([key,param])=><div className={s.meta} key={key}><dt>{param.label||key}</dt><dd>{param.description||param.type}{param.default!=null?` (${JSON.stringify(param.default)})`:''}</dd></div>)}</dl></>}
          </section>}
        </>}
        {view==='implementation'&&<MethodAssetEditor key={name} name={name} onPublished={reload}/>}
        {view==='executions'&&<MethodExecutions key={`${name}:${method.version}`} method={method}/>}
      </div>
    </>}
  </div>;
}
