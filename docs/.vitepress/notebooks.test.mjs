import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { notebookPaths, notebooks, renderNotebook } from './notebooks.mjs'

for (const entry of notebooks) {
  test(`${entry.language}: publish every code cell and saved text result`, () => {
    const notebook = JSON.parse(readFileSync(entry.path, 'utf8'))
    const [{ content, params }] = notebookPaths(entry.language)
    assert.equal(params.notebook, 'write-your-method')
    for (const cell of notebook.cells.filter(cell => cell.cell_type === 'code')) {
      assert.ok(content.includes(cell.source.join('').trimEnd()))
      for (const output of cell.outputs ?? []) {
        const value = output.text ?? output.data?.['text/plain']
        if (value) assert.ok(content.includes(value.join('').trimEnd()))
      }
    }
    assert.ok(!content.includes('../../guides/'))
    assert.ok(!content.includes('../../ko/guides/'))
    assert.ok(content.includes('/guides/method-projects'))
  })
}

test('output stays inside a code fence, including embedded fences and Vue text', () => {
  const content = renderNotebook({ cells: [{
    cell_type: 'code', source: ['print("hello")'], outputs: [{
      output_type: 'execute_result', data: {
        'text/html': '<script>alert(1)</script>',
        'text/plain': '```\n{{ dangerous() }}\n<script>inert text</script>',
      },
    }],
  }] }, 'en')
  assert.ok(content.includes('````text\n```\n{{ dangerous() }}\n<script>inert text</script>\n````'))
  assert.ok(!content.includes('alert(1)'))
})

test('a saved execution error fails the documentation build', () => {
  assert.throws(() => renderNotebook({ cells: [{
    cell_type: 'code', source: 'broken()', outputs: [{
      output_type: 'error', ename: 'ValueError', evalue: 'broken input',
    }],
  }] }, 'en'), /ValueError: broken input/)
})
