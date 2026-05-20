import { createFileRoute } from '@tanstack/react-router';
import { RegisterScreen } from '../features/operating/screens/RegisterScreen.js';

export const Route = createFileRoute('/workspace/register')({
  component: RegisterScreen,
});
