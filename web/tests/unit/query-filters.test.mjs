import test from 'node:test';
import assert from 'node:assert/strict';
import { completeFilters, filterOperators, filterValue } from '../../lib/query-filters.ts';

const objects = [
  {ref:'cube://sample/items/category',kind:'dimension',data_type:'string',public:true},
  {ref:'cube://sample/items/value',kind:'measure',data_type:'number',public:true},
  {ref:'cube://sample/items/active',kind:'dimension',data_type:'boolean',public:true},
];
const condition = (member, values, operator='equals') => ({member,operator,values});

test('typed inputs preserve zero, negatives and false in canonical filter values',()=>{
  assert.equal(filterValue('0','number'),0);
  assert.equal(filterValue('-2.5','number'),-2.5);
  assert.equal(filterValue('false','boolean'),false);
  assert.equal(filterValue('001','string'),'001');
  assert.equal(filterValue('-','number'),'-');
  assert.ok(completeFilters([condition(objects[1].ref,[0]),condition(objects[2].ref,[false])],objects));
});

test('unfinished, inaccessible and nonnumeric conditions cannot be submitted',()=>{
  assert.ok(completeFilters([],objects));
  for(const filters of [
    [condition('',[])], [condition(objects[0].ref,[])],
    [condition(objects[0].ref,['A',''])], [condition(objects[1].ref,['-'])],
    [condition(objects[1].ref,[Infinity])], [condition('cube://other/items/category',['A'])],
    [null],
  ]) assert.equal(completeFilters(filters,objects),false);
  assert.equal(completeFilters([condition(objects[0].ref,['A'])],[{...objects[0],public:false}]),false);
});

test('presence conditions do not retain ignored values and multiple group values stay intact',()=>{
  assert.ok(completeFilters([condition(objects[0].ref,[],'notSet')],objects));
  assert.equal(completeFilters([condition(objects[0].ref,['A'],'notSet')],objects),false);
  const filters=[condition(objects[0].ref,['A','B']),condition(objects[1].ref,[10],'gte')];
  const before=JSON.stringify(filters);
  assert.ok(completeFilters(filters,objects));
  assert.equal(JSON.stringify(filters),before);
  assert.ok(filterOperators('number').includes('gte'));
  assert.equal(filterOperators('boolean').includes('contains'),false);
});

test('runtime and ranked-step filter sources remain executable references',()=>{
  for(const source of [
    {source:'input',name:'scope'},
    {source:'step',step_id:'rank',output:'ranked_groups',project:'filters',select:'top',count:3},
  ]) assert.ok(completeFilters(source,objects));
  assert.equal(completeFilters({member:objects[0].ref},objects),false);
});
