const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('src/class_schedule/web/app.js', 'utf8');
const start = source.indexOf('let courseSortKey=');
const end = source.indexOf('function renderCourseList()', start);
const classes = [
  {sections:[{Subject:'MATH',Number:'5173',Section:'001',Instructor:'Zoe',Room:'Z'}, {Subject:'STAT',Number:'4173',Section:'001',Instructor:'Amy',Room:'A'}]},
  {sections:[{Subject:'MATH',Number:'2003',Section:'002',Instructor:'Carol',Room:'C'}]},
  {sections:[{Subject:'MATH',Number:'1003',Section:'001',Instructor:'Bob',Room:'B'}, {Subject:'MATH',Number:'0803',Section:'001',Instructor:'Bob',Room:'B'}]},
];
let input, edits=[], renders=0;
const button={dataset:{class:'2',record:'0',course:'MATH 1003'},handlers:{},addEventListener(name,handler){this.handlers[name]=handler;},replaceWith(value){input=value;}};
const ctx={assert,Intl,data:{classes},editBusy:false,busy:false,sections:()=>classes.flatMap((item,i)=>item.sections.map((r,j)=>({...r,_item:item,_classIndex:i,_recordIndex:j}))),isSplitLabKind:()=>false,instructorLabel:x=>x,roomLabel:x=>x.Room,document:{createElement:()=>({handlers:{},setAttribute(){},focus(){},select(){},addEventListener(name,handler){this.handlers[name]=handler;}})},$$:selector=>selector==='.section-number-button'?[button]:[],submitEdit:async(...args)=>{edits.push(args);},markDirty(){},renderIssues(){},renderWorkload(){},toast(){},renderCourseList(){renders++;},renderSchedule(){renders++;}};
vm.createContext(ctx);vm.runInContext(source.slice(start,end),ctx);
vm.runInContext(`
 assert.equal(courseSortKey,'course');
 assert.deepEqual(Array.from(sortedCourseRows(),r=>r._classIndex),[2,2,1,0,0]);
 courseSortKey='instructor';assert.deepEqual(Array.from(sortedCourseRows(),r=>r._classIndex),[0,0,2,2,1]);
 courseSortKey='room';assert.deepEqual(Array.from(sortedCourseRows(),r=>r._classIndex),[0,0,2,2,1]);
 courseSortDirection=-1;assert.deepEqual(Array.from(sortedCourseRows(),r=>r._classIndex),[1,2,2,0,0]);
 assert.equal(data.classes[0].sections[0].Number,'5173');
 bindSectionEditing();
`,ctx);
(async()=>{
 button.handlers.click();assert.equal(input.type,'text');assert.equal(input.value,'001');
 input.value='007';input.handlers.keydown({key:'Enter',preventDefault(){}});await new Promise(setImmediate);
 assert.deepEqual(edits,[[2,0,'section','007']]);assert.equal(ctx.editBusy,false);assert.equal(renders,1);
 button.handlers.click();input.value='008';input.handlers.keydown({key:'Escape',preventDefault(){}});await new Promise(setImmediate);
 assert.equal(edits.length,1);assert.equal(renders,2);
 button.handlers.click();input.value='009';input.handlers.blur();await new Promise(setImmediate);
 assert.deepEqual(edits[1],[2,0,'section','009']);
 console.log('Passed: atomic course/instructor/room sorting, reverse order, smallest course anchor, text editing, Enter, Escape and blur.');
})().catch(error=>{console.error(error);process.exitCode=1;});
