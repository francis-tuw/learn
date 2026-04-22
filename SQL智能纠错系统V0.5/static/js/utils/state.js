class AppState {
  constructor() {
    this.state = {
      system: {
        ollamaConnected: false,
        modelName: null,
        status: 'offline',
      },
      currentMode: 'single',
      files: {
        mapping: null,
        sql: null,
        sqlContent: '',
        sqlFilename: '',
      },
      singleTask: {
        taskId: null,
        status: 'idle',
        progress: 0,
        currentStep: 'idle',
        result: null,
      },
      batchTask: {
        batchId: null,
        pairStates: {},
        stats: { total: 0, completed: 0, running: 0, waiting: 0, errors: 0 },
        isPaused: false,
      },
      ui: {
        activeTab: 'single',
        businessExpanded: false,
        businessContent: '',
        findingsFilter: { type: 'all', status: 'all', search: '' },
      },
    };
    this.subscribers = new Map();
  }

  getState() {
    return this.state;
  }

  setState(path, value) {
    const keys = path.split('.');
    let current = this.state;
    for (let i = 0; i < keys.length - 1; i++) {
      if (!current[keys[i]]) current[keys[i]] = {};
      current = current[keys[i]];
    }
    const oldValue = current[keys[keys.length - 1]];
    current[keys[keys.length - 1]] = value;

    this.notify(path, value, oldValue);
  }

  subscribe(paths, callback) {
    const pathArray = Array.isArray(paths) ? paths : [paths];
    const id = Symbol('subscriber');
    this.subscribers.set(id, { paths: pathArray, callback });
    return () => this.subscribers.delete(id);
  }

  notify(path, value, oldValue) {
    for (const [, subscriber] of this.subscribers) {
      if (subscriber.paths.some((p) => path.startsWith(p) || p.startsWith(path))) {
        try {
          subscriber.callback(path, value, oldValue);
        } catch (e) {
          console.error('State subscriber error:', e);
        }
      }
    }
  }

  resetSingleTask() {
    this.state.singleTask = {
      taskId: null,
      status: 'idle',
      progress: 0,
      currentStep: 'idle',
      result: null,
    };
    this.notify('singleTask', this.state.singleTask);
  }

  resetBatchTask() {
    this.state.batchTask = {
      batchId: null,
      pairStates: {},
      stats: { total: 0, completed: 0, running: 0, waiting: 0, errors: 0 },
      isPaused: false,
    };
    this.notify('batchTask', this.state.batchTask);
  }

  updatePairState(pairId, updates) {
    if (!this.state.batchTask.pairStates[pairId]) {
      this.state.batchTask.pairStates[pairId] = {
        id: pairId,
        status: 'waiting',
        progress: 0,
        mappingFile: '',
        sqlFile: '',
      };
    }
    Object.assign(this.state.batchTask.pairStates[pairId], updates);

    const states = Object.values(this.state.batchTask.pairStates);
    this.state.batchTask.stats = {
      total: states.length,
      completed: states.filter((s) => s.status === 'done').length,
      running: states.filter((s) => s.status === 'parsing' || s.status === 'agents').length,
      waiting: states.filter((s) => s.status === 'waiting').length,
      errors: states.filter((s) => s.status === 'error').length,
    };

    this.notify(`batchTask.pairStates.${pairId}`, this.state.batchTask.pairStates[pairId]);
    this.notify('batchTask.stats', this.state.batchTask.stats);
  }
}

const appState = new AppState();
