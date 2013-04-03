#!/usr/bin/env python
"""
    Modified version of code examples from the chemfp project.
    http://code.google.com/p/chem-fingerprints/
    Thanks to Andrew Dalke of Andrew Dalke Scientific!
"""

import chemfp
from chemfp import search
import sys
import os
import tempfile
import argparse
import subprocess


def unix_sort(results):
    temp_unsorted = tempfile.NamedTemporaryFile(delete=False)
    for (i,indices) in enumerate( results.iter_indices() ):
        temp_unsorted.write('%s %s\n' % (len(indices), i))
    temp_unsorted.close()
    temp_sorted = tempfile.NamedTemporaryFile(delete=False)
    temp_sorted.close()
    p = subprocess.Popen(['sort', '-n', '-r', '-k', '1,1'], stdin=open(temp_unsorted.name), stdout=open(temp_sorted.name, 'w+'))
    stdout, stderr = p.communicate()
    return_code = p.returncode

    if return_code:
        sys.stdout.write(stdout)
        sys.stderr.write(stderr)
        sys.stderr.write("Return error code %i from command:\n" % return_code)
    temp_sorted.close()
    os.remove(temp_unsorted.name)

    for line in open(temp_sorted.name):
        size, fp_idx = line.strip().split()
        yield (int(size), int(fp_idx))

    os.remove(temp_sorted.name)


def butina( args ):
    """
        Taylor-Butina clustering from the chemfp help.
    """

    # make sure that the file ending is fps
    temp_file = tempfile.NamedTemporaryFile()
    temp_link = "%s.%s" % (temp_file.name, 'fps')
    temp_file.close()
    os.symlink(args.input_path, temp_link)
    #os.system('ln -s %s %s' % (args.input_path, temp_link) )

    out = args.output_path
    arena = chemfp.load_fingerprints( temp_link )

    chemfp.set_num_threads( args.processors )
    results = search.threshold_tanimoto_search_symmetric(arena, threshold = args.tanimoto_threshold)
    results.reorder_all("move-closest-first")

    # TODO: more memory efficient search?
    # Reorder so the centroid with the most hits comes first.
    # (That's why I do a reverse search.)
    # Ignore the arbitrariness of breaking ties by fingerprint index
    """
    results = sorted( (  (len(indices), i, indices)
                              for (i,indices) in enumerate(results.iter_indices()) ),
                      reverse=True)
    """
    sorted_ids = unix_sort(results)
    
    # Determine the true/false singletons and the clusters
    true_singletons = []
    false_singletons = []
    clusters = []

    seen = set()
    #for (size, fp_idx, members) in results:
    for (size, fp_idx) in sorted_ids:
        members = results[fp_idx].get_indices()

        if fp_idx in seen:
            # Can't use a centroid which is already assigned
            continue
        seen.add(fp_idx)

        if size == 1:
            # The only fingerprint in the exclusion sphere is itself
            true_singletons.append(fp_idx)
            continue

        # Figure out which ones haven't yet been assigned
        unassigned = set(members) - seen

        if not unassigned:
            false_singletons.append(fp_idx)
            continue

        # this is a new cluster
        clusters.append( (fp_idx, unassigned) )
        seen.update(unassigned)

    len_cluster = len(clusters)
    #out.write( "#%s true singletons: %s\n" % ( len(true_singletons), " ".join(sorted(arena.ids[idx] for idx in true_singletons)) ) )
    #out.write( "#%s false singletons: %s\n" % ( len(false_singletons), " ".join(sorted(arena.ids[idx] for idx in false_singletons)) ) )

    out.write( "#%s true singletons\n" % len(true_singletons) )
    out.write( "#%s false singletons\n" % len(false_singletons) )
    out.write( "#clusters: %s\n" % len_cluster )

    # Sort so the cluster with the most compounds comes first,
    # then by alphabetically smallest id
    def cluster_sort_key(cluster):
        centroid_idx, members = cluster
        return -len(members), arena.ids[centroid_idx]

    clusters.sort(key=cluster_sort_key)

    for centroid_idx, members in clusters:
        centroid_name = arena.ids[centroid_idx]
        out.write("%s\t%s\t%s\n" % (centroid_name, len(members), " ".join(arena.ids[idx] for idx in members)))
        #ToDo: len(members) need to be some biggest top 90% or something ...

    for idx in true_singletons:
        out.write("%s\t%s\n" % (arena.ids[idx], 0))

    out.close()
    os.remove( temp_link )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="""Taylor-Butina clustering for fps files.
For more details please see the original publication or the chemfp documentation:
http://www.chemomine.co.uk/dbclus-paper.pdf
https://chemfp.readthedocs.org
""")

    parser.add_argument("-i", "--input", dest="input_path",
                    required=True,
                    help="Path to the input file.")

    parser.add_argument("-o", "--output", dest="output_path", type=argparse.FileType('w'),
                    default=sys.stdout,
                    help="Path to the output file.")

    parser.add_argument("-t", "--threshold", dest="tanimoto_threshold", type=float,
                    default=0.8,
                    help="Tanimoto threshold [0.8]")

    parser.add_argument('-p', '--processors', type=int, 
        default=4)

    options = parser.parse_args()
    butina( options )


