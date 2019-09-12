Python Client for the WhatsApp Business API
===========================================

.. image:: https://circleci.com/gh/praekeltfoundation/python-whatsapp-business-client/tree/develop.svg?style=svg
    :target: https://circleci.com/gh/praekeltfoundation/python-whatsapp-business-client/tree/develop

This work is extracted from Praekelt PBC's work on MomConnect and WhatsApp.
See the `blog post`_ for more details.

This does not work with a normal WhatsApp account, only the WhatsApp Business API.

.. _blog post: https://medium.com/mobileforgood/praekelt-org-pilots-whatsapp-for-social-impact-19a336f5b04e

Also has some support for creating message templates and sending message templates in bulk.

.. code::

    $ pip install wabclient[cli]
    $ wabclient create --help
    $ wabclient create \
        --number <your number without leading + like `27123456789`> \
        --token <your auth token> \
        --name <template name> \
        --template <template>
        
    $ wabclient send --help
    $ wabclient send \
        --csv-file wa_ids.csv \
        --token your-auth-token \
        --namespace the-namespace \
        --name the-element-name \
        --rate-limit 60\60 \ 
        --param "the first HSM template default param" \
        --param "the second HSM template default param"

The CSV file should list the WA ids, one per line. WA ids are generally in the E.164 format without a leading plus.
If you're getting errors adding the `--debug` flag will print the JSON error response from the API to stderr.

For WA ids that were sent to successfully will be print in green to `stdout`, WA ids that are invalid will print to `stderr` in red.
