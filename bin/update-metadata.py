import os


def update_metadata(file_):
    print('processing {}'.format(file_))
    updated_lines = []
    with open(file_) as f:
        lines = f.readlines()
        in_metadata = False
        for line in lines:
            line = line.rstrip()

            if line == '---':
                updated_lines.append('+++')
                in_metadata = not in_metadata
                continue

            if in_metadata:
                try:
                    key, value = line.split(':', 1)
                    value = value.strip()
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    if key == 'date':
                        # e.g., "2012-09-09 23:11"
                        try:
                            date, time = value.split(' ')
                            value = '{}T{}:00'.format(date, time)
                        except:
                            # probably ok
                            pass

                    updated_lines.append('{} = "{}"'.format(key, value))
                    continue
                except:
                    import pdb
                    pdb.set_trace()  # XXX BREAKPOINT

            updated_lines.append(line)

    with open(file_, 'w') as f:
        f.write('\n'.join(updated_lines))


for root, dirs, files in os.walk('.'):
    for file_ in files:
        if file_.endswith('.markdown'):  # let's process it
            update_metadata(file_)
