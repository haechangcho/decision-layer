import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

export const notebooks = ['en', 'ko'].map(language => ({
  language,
  filename: `write_your_method.${language}.ipynb`,
  path: fileURLToPath(new URL(`../tutorials/methods/write_your_method.${language}.ipynb`, import.meta.url)),
}))

const text = value => Array.isArray(value) ? value.join('') : (value ?? '')

// Preserve output as inert text: notebook HTML/JavaScript must never become page code.
function fence(value, language) {
  const source = text(value).replace(/\x1b\[[0-9;]*m/g, '').trimEnd()
  const longest = Math.max(2, ...(source.match(/`+/g) ?? []).map(run => run.length))
  const delimiter = '`'.repeat(longest + 1)
  return `${delimiter}${language}\n${source}\n${delimiter}`
}

export function renderNotebook(notebook, language) {
  const ko = language === 'ko'
  const filename = `write_your_method.${language}.ipynb`
  const source = `https://github.com/haechangcho/decision-layer/blob/main/docs/tutorials/methods/${filename}`
  const tools = ko
    ? `<a href="/notebooks/${filename}" download>노트북 다운로드</a> | [GitHub에서 보기](${source})\n\n노트북에 저장된 코드와 실행 결과를 보여줍니다. 직접 실행하려면 [개발 환경](/ko/guides/development)을 준비하고 저장소의 \`docs/tutorials/methods\`에서 노트북을 여세요.`
    : `<a href="/notebooks/${filename}" download>Download notebook</a> | [View on GitHub](${source})\n\nThis page shows the code and saved outputs. To run it, [set up the repository](/guides/development) and open the notebook in \`docs/tutorials/methods\`.`
  let firstMarkdown = true
  return notebook.cells.map(cell => {
    if (cell.cell_type === 'markdown') {
      let content = text(cell.source)
        .replaceAll('write_your_method.en.ipynb', '/tutorials/write-your-method')
        .replaceAll('write_your_method.ko.ipynb', '/ko/tutorials/write-your-method')
        .replaceAll('../../ko/guides/', '/ko/guides/')
        .replaceAll('../../guides/', '/guides/')
        .replaceAll('.md)', ')')
      if (firstMarkdown) {
        content = content.replace(/^(# .+)$/m, `$1\n\n${tools}`)
        firstMarkdown = false
      }
      return content
    }
    if (cell.cell_type !== 'code') return ''
    const output = (cell.outputs ?? []).flatMap(item => {
      if (item.output_type === 'error') {
        throw new Error(`Notebook contains a saved error: ${item.ename}: ${item.evalue}`)
      }
      const value = item.output_type === 'stream' ? item.text : item.data?.['text/plain']
      return value == null ? [] : [fence(value, 'text')]
    })
    return [fence(cell.source, 'python'), ...output.length ? [
      `<p class="notebook-output-label">${ko ? '실행 결과' : 'Output'}</p>`, ...output,
    ] : []].join('\n\n')
  }).join('\n\n')
}

export function notebookPaths(language) {
  const entry = notebooks.find(item => item.language === language)
  return [{
    params: { notebook: 'write-your-method' },
    content: renderNotebook(JSON.parse(readFileSync(entry.path, 'utf8')), language),
  }]
}

// The same original files are downloadable in development and in the static build.
export function notebookDownloads() {
  return {
    name: 'decision-layer:notebook-downloads',
    configureServer(server) {
      server.watcher.add(notebooks.map(entry => entry.path))
      server.middlewares.use((request, response, next) => {
        const entry = notebooks.find(item => request.url?.split('?')[0] === `/notebooks/${item.filename}`)
        if (!entry) return next()
        response.setHeader('Content-Type', 'application/x-ipynb+json; charset=utf-8')
        response.setHeader('Content-Disposition', `attachment; filename="${entry.filename}"`)
        response.end(readFileSync(entry.path))
      })
    },
    async handleHotUpdate(context) {
      if (notebooks.some(entry => entry.path === context.file)) {
        await context.server.restart()
        return []
      }
    },
    generateBundle() {
      for (const entry of notebooks) {
        this.emitFile({ type: 'asset', fileName: `notebooks/${entry.filename}`, source: readFileSync(entry.path) })
      }
    },
  }
}
