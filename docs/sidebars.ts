import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

/**
  * Creating a sidebar enables you to:
  - create an ordered group of docs
  - render a sidebar for each doc of that group
  - provide next/previous navigation

  The sidebars can be generated from the filesystem, or explicitly defined here.

  Create as many sidebars as you want.
 */
const sidebars: SidebarsConfig = {
  docsSidebar: [
    'readme',
    {
      type: 'category',
      label: 'Infrahub Overview',
      link: {type: 'doc', id: 'overview/readme'},
      items: [
        'overview/interfaces',
        'overview/schema',
        'overview/data',
      ],
    },
    {
      'Tutorials': [
        {
          type: 'category',
          label: 'Getting started',
          link: {type: 'doc', id: 'tutorials/getting-started/readme'},
          items: [
            'tutorials/getting-started/introduction-to-infrahub',
            'tutorials/getting-started/schema',
            'tutorials/getting-started/creating-an-object',
            'tutorials/getting-started/branches',
            'tutorials/getting-started/historical-data',
            'tutorials/getting-started/lineage-information',
            'tutorials/getting-started/git-integration',
            'tutorials/getting-started/jinja2-integration',
            'tutorials/getting-started/custom-api-endpoint',
            'tutorials/getting-started/graphql-query',
            'tutorials/getting-started/graphql-mutation'
          ],
        },
      ],
    },
    {
      type: 'category',
      label: 'Guides',
      link: {
        type: 'generated-index',
        slug: 'guides'
      },
      items: [
        'guides/installation',
        'guides/create-schema',
        'guides/generator',
        'guides/repository',
        'guides/jinja2-transform',
        'guides/python-transform',
        'guides/artifact',
        'guides/database-backup',
        'guides/profiles',
        'guides/object-storage',
	'guides/check',
      ],
    },
    {
      type: 'category',
      label: 'Topics',
      link: {
        type: 'generated-index',
        slug: 'topics'
      },
      items: [
        'topics/infrahub-yml',
        'topics/architecture',
        'topics/artifact',
        'topics/check',
        'topics/hardware-requirements',
        'topics/ipam',
        'topics/local-demo-environment',
        'topics/generator',
        'topics/graphql',
        'topics/object-storage',
        'topics/version-control',
        'topics/proposed-change',
        'topics/repository',
        'topics/schema',
        'topics/transformation',
        'topics/auth',
        'topics/database-backup',
        'topics/resources-testing-framework',
        'topics/profiles',
      ],
    },
    {
      type: 'category',
      label: 'Reference',
      link: {
        type: 'generated-index',
        slug: 'reference'
      },
      items: [
        {
          type: 'category',
          label: 'Schema',
          link: {
            type: 'generated-index',
            slug: 'reference/schema',
          },
          items: [
            'reference/schema/node',
            'reference/schema/node-extension',
            'reference/schema/attribute',
            'reference/schema/relationship',
            'reference/schema/generic',
            'reference/schema/validator-migration',
          ],
        },
        {
          type: 'category',
          label: 'infrahub cli',
          link: {
            type: 'generated-index',
            slug: 'reference/infrahub-cli',
          },
          items: [
            'reference/infrahub-cli/infrahub-db',
            'reference/infrahub-cli/infrahub-git-agent',
            'reference/infrahub-cli/infrahub-server'
          ],
        },
        'reference/configuration',
        'reference/git-agent',
        'reference/message-bus-events',
        'reference/api-server',
        'reference/dotinfrahub',
        'reference/infrahub-tests',
        'reference/schema-validation'
      ],
    },
    {
      type: 'category',
      label: 'Python SDK',
      link: {
        type: 'doc',
        id: 'python-sdk/readme'
      },
      items: [
        {
          type: 'category',
          label: 'Guides',
          items: [
            'python-sdk/guides/installation',
            'python-sdk/guides/client',
            'python-sdk/guides/query_data',
            'python-sdk/guides/create_update_delete',
            'python-sdk/guides/branches',
            'python-sdk/guides/store',
            'python-sdk/guides/tracking',
            'python-sdk/guides/batch',
            'python-sdk/guides/object-storage'
          ],
        },
        {
          type: 'category',
          label: 'Topics',
          items: [
            'python-sdk/topics/tracking'
          ],
        },
        {
          type: 'category',
          label: 'Reference',
          items: [
            'python-sdk/reference/config'
          ],
        },
      ],
    },
    {
      type: 'category',
      label: 'infrahubctl',
      link: {type: 'doc', id: 'infrahubctl'},
      items: [{type: 'autogenerated', dirName: 'infrahubctl' }],
    },
    {
      type: 'category',
      label: 'Integrations',
      link: {
        type: 'doc',
        id: 'integrations/readme'
      },
      items: [
        {
          type: 'category',
          label: 'Infrahub Ansible Collection',
          link: {
            type: 'doc',
            id: 'integrations/infrahub-ansible/readme'
          },
          items: [
            {
            },
          ],
        },
        {
          type: 'category',
          label: 'Infrahub Sync',
          link: {
            type: 'doc',
            id: 'integrations/sync/readme'
          },
          items: [
            {
              type: 'category',
              label: 'Guides',
              items: [
                'integrations/sync/guides/installation',
                'integrations/sync/guides/creation',
                'integrations/sync/guides/run',
              ],
            },
            {
              type: 'category',
              label: 'Reference',
              items: [
                'integrations/sync/reference/config',
                'integrations/sync/reference/cli',
              ],
            },
          ],
        },
        {
          type: 'category',
          label: 'Nornir plugin for Infrahub',
          link: {
            type: 'doc',
            id: 'integrations/nornir-infrahub/readme'
          },
          items: [
            {
            },
          ],
        },
      ]
    },
    {
      type: 'category',
      label: 'Development',
      link: {type: 'doc', id: 'development/readme'},
      items: [
        'development/editor',
        'development/backend',
        {
          type: 'category',
          label: 'Frontend guide',
          link: {type: 'doc', id: 'development/frontend/readme'},
          items: [
            'development/frontend/getting-set-up',
            'development/frontend/testing-guidelines',
          ],
        },
        'development/docs'
      ],
    },
    {
      'Release Notes': [
        'release-notes/release-0_14',
        'release-notes/release-0_13',
        'release-notes/release-0_12',
        'release-notes/release-0_11',
        'release-notes/release-0_10',
        'release-notes/release-0_9',
        'release-notes/release-0_8',
        'release-notes/release-0_7',
        'release-notes/release-0_6'],
    },
    'faq/faq',
  ],
};

export default sidebars;
