"""Tk desktop form for independent Windows and macOS observation processing."""
from datetime import datetime
from pathlib import Path
import json
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from .ui_text import text
from .desktop_job import prepare_job,start_job,cancel_job,open_folder


class App:
    def __init__(self,root):
        self.root=root;self.process=None;self.output=None;self.fields={};self.labels=[];self.combos=[]
        self.ui_language=tk.StringVar(value="中文");self.status_key="idle"
        root.title('Occultation Media — 掩星动画生成器');root.geometry('1080x850');root.minsize(1020,800)
        body=ttk.Frame(root,padding=18);body.pack(fill='both',expand=True)
        top=ttk.Frame(body);top.pack(fill='x')
        self.label(top,'title',font=('',21,'bold')).pack(side='left')
        ttk.Label(top,text='界面语言 / Interface').pack(side='right',padx=8)
        selector=ttk.Combobox(top,textvariable=self.ui_language,values=('中文','English'),state='readonly',width=10)
        selector.pack(side='right');selector.bind('<<ComboboxSelected>>',self.change_language)
        self.label(body,'subtitle').pack(anchor='w',pady=(4,12))
        files=self.label(body,'files',kind=ttk.LabelFrame,padding=10);files.pack(fill='x')
        for key,label in [('source','观测文件'),('csv','Tangra CSV'),('output','输出文件夹')]:
            row=ttk.Frame(files);row.pack(fill='x',pady=3)
            self.label(row,key,width=16).pack(side='left')
            var=tk.StringVar();self.fields[key]=var
            ttk.Entry(row,textvariable=var).pack(side='left',fill='x',expand=True)
            self.label(row,'browse',kind=ttk.Button,command=lambda k=key:self.choose(k)).pack(side='left',padx=(6,0))
            if key=='source':self.label(row,'fits_folder',kind=ttk.Button,command=self.choose_fits).pack(side='left',padx=(6,0))
        form=self.label(body,'observation',kind=ttk.LabelFrame,padding=10);form.pack(fill='x',pady=10)
        entries=[('asteroid','小行星名称',''),('star','目标星名称','Target'),
                 ('date','事件日期 YYYY-MM-DD',datetime.utcnow().strftime('%Y-%m-%d')),
                 ('predicted','预报中点 HH:MM:SS',''),('uncertainty','预报 ± 误差（秒）',''),
                 ('exposure','曝光时间（毫秒）',''),('first','源第 0 帧对应的 CSV 帧号','0'),
                 ('margin','事件前后各保留（秒）','5')]
        for i,(key,label,value) in enumerate(entries):
            r,c=divmod(i,2);self.add_entry(form,r,c*2,key,label,value)
        for c in (1,3):form.columnconfigure(c,weight=1)
        self.label(form,'mapping',wraplength=980).grid(row=4,column=0,columnspan=4,sticky='w',pady=(8,0))
        more=self.label(body,'optional',kind=ttk.LabelFrame,padding=10);more.pack(fill='x')
        for i,(key,label,value) in enumerate([('low','首末低光通量帧号（可留空）',''),('target','目标像素 X Y（可留空）',''),
                                              ('stride','每 N 帧显示一帧','1'),('hdu','FITS HDU（可留空）','')]):
            r,c=divmod(i,2);self.add_entry(more,r,c*2,key,label,value)
        for c in (1,3):more.columnconfigure(c,weight=1)
        row=ttk.Frame(more);row.grid(row=2,column=0,columnspan=4,sticky='w',pady=6)
        for key,label,options,default in [('language','输出语言',('both','zh','en'),'both'),('byte_order','SER 字节序',('header','little','big'),'header')]:
            self.label(row,key).pack(side='left',padx=(0,6));var=tk.StringVar(value=default);self.fields[key]=var
            display=tk.StringVar(value=self.tr(default))
            combo=ttk.Combobox(row,textvariable=display,values=[self.tr(o) for o in options],state='readonly',width=18)
            combo.pack(side='left',padx=(0,18))
            combo.bind('<<ComboboxSelected>>',lambda event,v=var,c=combo,o=options:v.set(o[c.current()]))
            self.combos.append((combo,display,var,options))
        self.fields['mp4']=tk.BooleanVar(value=True)
        self.label(row,'mp4',kind=ttk.Checkbutton,variable=self.fields['mp4']).pack(side='left')
        self.label(body,'stretch',wraplength=980).pack(anchor='w',pady=(10,3))
        actions=ttk.Frame(body);actions.pack(fill='x',pady=6)
        self.generate=self.label(actions,'generate',kind=ttk.Button,command=self.start);self.generate.pack(side='left')
        self.cancel=self.label(actions,'cancel',kind=ttk.Button,command=self.stop,state='disabled');self.cancel.pack(side='left',padx=8)
        self.reveal=self.label(actions,'reveal',kind=ttk.Button,command=lambda:open_folder(self.output),state='disabled');self.reveal.pack(side='left')
        self.status=tk.StringVar(value=self.tr('idle'))
        ttk.Label(body,textvariable=self.status,wraplength=900).pack(anchor='w')
        self.progress=ttk.Progressbar(body,mode='indeterminate');self.progress.pack(fill='x',pady=6)
        self.log=tk.Text(body,height=6,wrap='word',state='disabled');self.log.pack(fill='both',expand=True)
        root.protocol('WM_DELETE_WINDOW',self.close)
        self.change_language()

    def tr(self,key):
        return text(key,'zh' if self.ui_language.get()=='中文' else 'en')

    def label(self,parent,key,kind=ttk.Label,**options):
        widget=kind(parent,text=self.tr(key),**options);self.labels.append((widget,key))
        return widget

    def change_language(self,event=None):
        # Configure existing widgets: input values and running jobs survive.
        for widget,key in self.labels:widget.configure(text=self.tr(key))
        for combo,display,value,options in self.combos:
            combo.configure(values=[self.tr(o) for o in options]);display.set(self.tr(value.get()))
        self.root.title('Occultation Media — '+self.tr('title') if self.ui_language.get()=='中文' else 'Occultation Media')
        self.status.set(self.tr(self.status_key))

    def set_status(self,key):
        self.status_key=key;self.status.set(self.tr(key))

    def error_text(self,error):
        key=str(error)
        return self.tr(key) if key.startswith('err_') else self.tr('unexpected')+' '+key

    def add_entry(self,parent,row,column,key,label,value):
        self.label(parent,key).grid(row=row,column=column,sticky='w',padx=(0,8),pady=4)
        var=tk.StringVar(value=value);self.fields[key]=var
        ttk.Entry(parent,textvariable=var,width=20).grid(row=row,column=column+1,sticky='ew',padx=(0,18),pady=4)

    def choose(self,key):
        if key=='output':value=filedialog.askdirectory(title=self.tr('output'))
        elif key=='csv':value=filedialog.askopenfilename(filetypes=[('Tangra CSV','*.csv'),(self.tr('all_files'),'*')])
        else:value=filedialog.askopenfilename(filetypes=[(self.tr('source'),'*.adv *.ser *.fits *.fit *.fts *.ravf *.lc'),(self.tr('all_files'),'*')])
        if value:
            self.fields[key].set(value)
            if key=='source' and not self.fields['output'].get():self.fields['output'].set(str(Path(value).parent/'media'))

    def choose_fits(self):
        value=filedialog.askdirectory(title=self.tr('fits_prompt'))
        if value:self.fields['source'].set(value)

    def start(self):
        try:
            argv,self.output=prepare_job({k:v.get() for k,v in self.fields.items()})
            self.process=start_job(argv,self.output)
        except Exception as error:messagebox.showerror(self.tr('cannot_start'),self.error_text(error));return
        self.generate.config(state='disabled');self.cancel.config(state='normal');self.reveal.config(state='normal')
        self.progress.start();self.set_status('running');self.poll()

    def poll(self):
        log=self.output/'run.log'
        if log.exists():
            self.log.config(state='normal');self.log.delete('1.0','end')
            self.log.insert('end',log.read_text(encoding='utf-8',errors='replace')[-12000:]);self.log.see('end');self.log.config(state='disabled')
        if self.process.poll() is None:self.root.after(500,self.poll);return
        self.progress.stop();self.generate.config(state='normal');self.cancel.config(state='disabled')
        result=self.output/'result.json'
        if result.exists():
            data=json.loads(result.read_text(encoding='utf-8'))
            self.set_status('done' if data['ok'] else 'failed')
        else:self.set_status('ended')

    def stop(self):
        if self.process:cancel_job(self.process)

    def close(self):
        if self.process and self.process.poll() is None:self.stop()
        self.root.destroy()


def run(smoke=False):
    root=tk.Tk();App(root)
    if smoke:root.after(1500,root.destroy)
    root.mainloop()
