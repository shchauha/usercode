import os
from argparse import Namespace

hostname = os.getenv('HOSTNAME')

_AT_UMD = ( hostname.count('umd') > 0 )


command_base = 'python scripts/filter.py  --filesDir %(base)s/%(input)s/%(sample)s/%(version)s --outputDir %(output)s/%(outsample)s --outputFile tree.root --treeName %(treename)s --fileKey %(filekey)s --module scripts/%(module)s --moduleArgs "%(moduleArgs)s"  --confFileName %(sample)s.txt --nFilesPerJob %(nFilesPerJob)d --exeName %(exename)s'

check_base = 'python ../../Util/scripts/check_dataset_completion.py --originalDS %(base)s/%(input)s/%(sample)s/%(version)s --filteredDS %(output)s/%(outsample)s --treeNameOrig %(treename)s --histNameFilt tupel/filter --fileKeyOrig %(filekey)s --fileKeyFilt tree.root'

def RunJobs( jobs, configs, options, dry_run=False ) :

    if not isinstance( jobs, list ) :
        jobs = [jobs]
    if not isinstance( configs, list ) :
        configs = [configs]

    if isinstance( options, Namespace ) :
        options = vars(options)

    jobs_data = []
    jobs_mc   = []

    for j in jobs : 
        if j.isData :
            jobs_data.append(j)
        else :
            jobs_mc.append(j)


    run                = options.get('run'                , False         )
    check              = options.get('check'              , False         )
    exename            = options.get('exename'            , 'RunAnalysis' )
    nFilesPerJob       = options.get('nFilesPerJob'       , 0             )
    filekey            = options.get('filekey'            , 'tree.root'   )
    treename           = options.get('treename'           , None          )
    copyInputFiles     = options.get('copyInputFiles'     , False         )
    batch              = options.get('batch'              , False         )
    nproc              = options.get('nproc'              , 1             )
    resubmit           = options.get('resubmit'           , False         )
    enableKeepFilter   = options.get('enableKeepFilter'   , False         )
    enableRemoveFilter = options.get('enableRemoveFilter' , False         ) 
    disableOutputTree  = options.get('disableOutputTree'  , False         )

    if run :
        for config in configs :
            first_data = True
            first_mc = True
    
            for job in jobs_data :
                job_exename = '%s_Data_%s' %(exename, config['tag'] )
    
                module_arg = dict(config.get('args', {}))
                module_arg['isData'] = 'true'
                module_str = '{ '
                # build the module string
                for key, val in module_arg.iteritems() :
                    if isinstance( val, basestring ) :
                        module_str += '\'%s\' : \'%s\',' %( key, val)
                    else :
                        module_str += '\'%s\' : %s,' %( key, val)
                module_str += '}'

                outsample = job.sample
                suffix = getattr(job, 'suffix', None )
                if suffix is not None :
                    outsample = outsample+suffix
    
                command = command_base %{ 'base' : job.base, 'sample' : job.sample, 'outsample' : outsample, 'nFilesPerJob' : nFilesPerJob, 'input' : config['input'], 'output' : config['output'], 'exename' : job_exename, 'treename' : treename, 'module' : config['module'], 'moduleArgs' : module_str, 'version' : job.version, 'filekey' : filekey }

                if enableKeepFilter :
                    command += ' --enableKeepFilter '
                if enableRemoveFilter :
                    command += ' --enableRemoveFilter '
                if disableOutputTree :
                    command += ' --disableOutputTree'

                if batch :
                    if _AT_UMD :
                        command += ' --condor '
                    else :
                        command += ' --batch '

                    if copyInputFiles :
                        command += ' --copyInputFiles '
                else :
                    command += ' --nproc %d ' %nproc

                if resubmit :
                    command += ' --resubmit '
    
                if not first_data :
                    command += ' --noCompileWithCheck '
    
                print command
                if not dry_run :
                    os.system(command)
                if first_data :
                    first_data = False
    
            for job in jobs_mc :
                job_exename = '%s_MC_%s' %(exename, config['tag'] )
    
                module_arg = dict(config.get('args', {}) )
    
                module_str = '{ '
                for key, val in module_arg.iteritems() :
                    if isinstance( val, basestring ) :
                        module_str += '\'%s\' : \'%s\',' %( key, val)
                    else :
                        module_str += '\'%s\' : %s,' %( key, val)
    
                module_str += '}'
    
                outsample = job.sample
                suffix = getattr(job, 'suffix', None )
                if suffix is not None :
                    outsample = outsample+suffix

                command = command_base %{ 'base' : job.base, 'sample' : job.sample, 'outsample' : outsample, 'nFilesPerJob' : nFilesPerJob, 'input' : config['input'], 'output' : config['output'], 'exename' : job_exename, 'treename' : treename, 'module' : config['module'], 'moduleArgs' : module_str, 'version' : job.version, 'filekey' : filekey }

                if enableKeepFilter :
                    command += ' --enableKeepFilter '
                if enableRemoveFilter :
                    command += ' --enableRemoveFilter '
                if disableOutputTree :
                    command += ' --disableOutputTree'

                if not first_mc :
                    command += ' --noCompileWithCheck '
    
                if batch :
                    if _AT_UMD :
                        command += ' --condor '
                    else :
                        command += ' --batch '

                    if copyInputFiles :
                        command += ' --copyInputFiles '
                else :
                    command += ' --nproc %d ' %nproc

                if resubmit :
                    command += ' --resubmit '
    
                print command
                if not dry_run :
                    os.system(command)
                if first_mc :
                    first_mc = False
    
    if check :
        for config in configs :
        
            for  job in (jobs_data + jobs_mc) :
        
                outsample = job.sample
                suffix = getattr(job, 'suffix', None )
                if suffix is not None :
                    outsample = outsample+suffix

                command = check_base%{ 'base': job.base , 'sample' : job.sample, 'outsample' : outsample, 'output' : config['output'], 'input' : config['input'], 'treename' : treename, 'version' : job.version, 'filekey' : filekey}
                print command                                                                               
                os.system(command)                                                                          

class JobConf( ) :

    def __init__( self, base, sample, **kwargs) :
        self.base    = base
        self.sample  = sample

        input_args = dict(kwargs)

        self.version = input_args.pop('version','')
        self.isData  = input_args.pop('isData', False)

        for key, val in input_args.iteritems() :
            setattr( self, key, val)
        


