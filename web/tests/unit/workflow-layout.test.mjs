import test from 'node:test';
import assert from 'node:assert/strict';
import { workflowLayout } from '../../components/workflow-layout.ts';

test('a six-node procedure fits a readable two-row overview on a wide pane',()=>{
 const layout=workflowLayout(6,1000);
 assert.equal(layout.columns,3);assert.equal(layout.rows,2);assert.equal(layout.readableOverview,true);
 assert.equal(layout.positions[2].exit,'bottom');assert.equal(layout.positions[3].entry,'top');
 assert.equal(layout.positions[3].x,layout.positions[2].x);
 assert.ok(layout.positions[4].x<layout.positions[3].x);
 assert.ok(layout.height<=450);
});
test('narrow panes choose the list and never need a taller-than-page viewport',()=>{
 for(const width of [320,390,557,700]){
  const layout=workflowLayout(13,width);assert.equal(layout.readableOverview,false);assert.ok(layout.height<=600);
  assert.equal(new Set(layout.positions.map(p=>`${p.x},${p.y}`)).size,13);
 }
});
test('layout does not mutate numbering and camera height is bounded for large histories',()=>{
 const layout=workflowLayout(100,1500);assert.equal(layout.positions.length,100);assert.equal(layout.height,600);assert.equal(layout.readableOverview,false);
 for(let i=1;i<layout.positions.length;i++){
  const a=layout.positions[i-1],b=layout.positions[i];
  assert.ok(a.y===b.y||b.y-a.y===208);
  if(a.y!==b.y){assert.equal(a.exit,'bottom');assert.equal(b.entry,'top');assert.equal(a.x,b.x);}
 }
});
